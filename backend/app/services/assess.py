"""技术评定业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "assess"
REQUIRED_FIELDS = ["评定编号", "评定对象", "评定周期"]
STATUS_ORDER = ["待评定", "评定中", "已定级", "已复评"]
ACTION_RULES = {"开始评定": "评定中", "确认定级": "已定级", "发起复评": "已复评"}
NEGATIVE_ACTIONS: list[str] = []
# 定级与复评都会改写生效结论，技术等级、评定结论缺一不可
FINALIZE_ACTIONS = {"确认定级", "发起复评"}
CONCLUSION_REQUIRED_FIELDS = ["技术等级", "评定结论"]
# 提交时允许落到记录上的结论字段；空值不覆盖已生效内容
CONCLUSION_FIELDS = ["技术等级", "评定结论", "评定人员", "评定日期"]


class AssessService:
    def __init__(self) -> None:
        self._ensure_history()

    def _ensure_history(self) -> None:
        """给既有评定记录补齐结论历史，老数据的历史结论照旧可读、不被覆盖。"""
        changed = False
        for row in store.rows(MODULE):
            status = str(row.get("status") or STATUS_ORDER[0])
            if row.get("评定状态") != status:
                row["评定状态"] = status
                changed = True
            if not isinstance(row.get("history"), list):
                row["history"] = []
                changed = True
            history = row["history"]
            conclusion = str(row.get("评定结论") or "").strip()
            if conclusion and not history:
                history.append({
                    "动作": "历史结论",
                    "技术等级": row.get("技术等级"),
                    "评定结论": row.get("评定结论"),
                    "评定人员": row.get("评定人员"),
                    "评定日期": row.get("评定日期"),
                    "记录时间": str(row.get("评定日期") or ""),
                })
                changed = True
        if changed:
            store.save()

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("评定编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["评定状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["history"] = []
        rows.append(entry)
        store.save()
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"评定记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于技术评定可执行范围"
        target = ACTION_RULES[action]
        current = str(entry.get("status") or STATUS_ORDER[0])
        if STATUS_ORDER.index(target) < STATUS_ORDER.index(current):
            return None, f"评定记录当前为{current}，不能回退到{target}"
        if action in FINALIZE_ACTIONS:
            missing = [
                field
                for field in CONCLUSION_REQUIRED_FIELDS
                if not str(values.get(field) or "").strip()
            ]
            if missing:
                level = str(entry.get("技术等级") or "").strip() or "未设置"
                return None, f"结论未生效：{'、'.join(missing)}不能为空，已保留原技术等级「{level}」"
        # 结论字段只在新值非空时覆盖，空提交不会清掉已生效的内容
        for field in CONCLUSION_FIELDS:
            text = str(values.get(field) or "").strip()
            if text:
                entry[field] = text
        entry["status"] = target
        entry["评定状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        if action in FINALIZE_ACTIONS:
            # 每次定级、复评都追加一条历史，同一条记录重复提交只以最新结论为准
            entry.setdefault("history", []).append({
                "动作": action,
                "技术等级": entry.get("技术等级"),
                "评定结论": entry.get("评定结论"),
                "评定人员": entry.get("评定人员"),
                "评定日期": entry.get("评定日期"),
                "记录时间": datetime.now().isoformat(timespec="seconds"),
            })
        store.save()
        level = str(entry.get("技术等级") or "").strip()
        if action in FINALIZE_ACTIONS and level:
            return entry, f"评定记录已{action}，技术等级落定为「{level}」"
        return entry, f"评定记录已{action}"
