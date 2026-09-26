"""数据仓库：内存表 + JSON 快照持久化。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
业务变更通过 save() 落到快照文件，重启或退出再进入后从快照恢复，结论不会回退。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.seed import SEED_ROWS

DEFAULT_STORE_FILE = Path(__file__).resolve().parent.parent / "data" / "store.json"


class Store:
    def __init__(self, store_file: Path | None = None) -> None:
        env_path = os.environ.get("APP_STORE_FILE", "").strip()
        self._store_file = Path(env_path) if env_path else Path(store_file or DEFAULT_STORE_FILE)
        self._tables: dict[str, list[dict[str, Any]]] = self._load()

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        """优先从快照恢复；快照缺失或损坏时回退到示例数据，保证服务起得来。"""
        if self._store_file.exists():
            data: Any = None
            try:
                data = json.loads(self._store_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = None
            if isinstance(data, dict):
                tables = {
                    str(name): [dict(row) for row in rows]
                    for name, rows in data.items()
                    if isinstance(rows, list)
                }
                if tables:
                    return tables
        return {name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()}

    def save(self) -> None:
        """把当前全量数据原子写入快照，避免写一半留下损坏文件。"""
        self._store_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self._store_file.with_name(self._store_file.name + ".tmp")
        tmp_file.write_text(
            json.dumps(self._tables, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_file.replace(self._store_file)

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
