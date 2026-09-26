"""技术评定业务规则：状态流转、字段校验与筛选口径都收在这里。

定级与复评的写入口径：
- 状态只能向前走（待评定 → 评定中 → 已定级 → 已复评），已复评不允许回退到评定中；
- 确认定级、发起复评必须带技术等级与评定结论，为空则整条提交不生效，保留原等级；
- 每次生效的结论都会追加到 history，旧结论只读保留，不被新提交覆盖；
- 同一记录重复提交时，记录上的等级与结论永远是最新一次的内容。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "assess"
REQUIRED_FIELDS = ["评定编号", "评定对象", "评定周期"]
STATUS_ORDER = ["待评定", "评定中", "已定级", "已复评"]
# 动作 → (允许的来源状态, 目标状态, 是否需要结论)
ACTION_FLOW: dict[str, tuple[set[str], str, bool]] = {
    "开始评定": ({"待评定"}, "评定中", False),
    "确认定级": ({"评定中", "已定级"}, "已定级", True),
    "发起复评": ({"已定级", "已复评"}, "已复评", True),
}
CONCLUSION_FIELDS = ["技术等级", "评定结论"]
FINAL_STATUS = STATUS_ORDER[-1]


class AssessService:
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

    def grade_summary(self) -> list[dict[str, Any]]:
        """运营概览用的技术等级一览：与列表、详情读同一份数据，保证三处一致。"""
        return [
            {
                "id": row.get("id"),
                "评定编号": row.get("评定编号"),
                "评定对象": row.get("评定对象"),
                "技术等级": row.get("技术等级") or "未评定",
                "评定状态": row.get("status"),
            }
            for row in store.rows(MODULE)
        ]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["技术等级"] = ""
        entry["评定结论"] = ""
        entry["评定人员"] = str(values.get("评定人员") or "").strip()
        entry["评定日期"] = ""
        entry["status"] = STATUS_ORDER[0]
        entry["评定状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["history"] = []
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"评定记录 {entry_id} 不存在或已归档"
        if action not in ACTION_FLOW:
            return None, f"动作「{action}」不属于技术评定可执行范围"

        current = str(entry.get("status") or STATUS_ORDER[0])
        sources, target, needs_conclusion = ACTION_FLOW[action]
        if current == FINAL_STATUS and target != FINAL_STATUS:
            return None, f"评定记录{FINAL_STATUS}，不能回退到{target}"
        if current not in sources:
            allowed = "、".join(sorted(sources))
            return None, f"当前状态「{current}」不能执行「{action}」，仅「{allowed}」状态可执行"

        values = values or {}
        if needs_conclusion:
            invalid = [field for field in CONCLUSION_FIELDS if not str(values.get(field) or "").strip()]
            if invalid:
                kept = entry.get("技术等级") or "未评定"
                return None, (
                    f"以下项目不合规：{'、'.join(invalid)}为空；"
                    f"本次提交未生效，仍保留原技术等级「{kept}」"
                )

        history = entry.setdefault("history", [])
        if needs_conclusion:
            self._snapshot_existing(entry, history)
            self._apply_conclusion(entry, values)
            message = self._append_history(entry, history, action)
        else:
            message = ""

        entry["status"] = target
        entry["评定状态"] = target
        entry["pending"] = target in STATUS_ORDER[:2]
        entry["abnormal"] = False
        return entry, message or f"评定记录已{action}"

    @staticmethod
    def _snapshot_existing(entry: dict[str, Any], history: list[dict[str, Any]]) -> None:
        """首次写入新结论前，把记录上既有结论留档，保证历史结论照旧可读。"""
        if history or not str(entry.get("评定结论") or "").strip():
            return
        history.append({
            "动作": "既有结论",
            "技术等级": entry.get("技术等级") or "",
            "评定结论": entry.get("评定结论"),
            "评定人员": entry.get("评定人员") or "",
            "记录时间": entry.get("评定日期") or datetime.now().isoformat(timespec="seconds"),
        })

    @staticmethod
    def _apply_conclusion(entry: dict[str, Any], values: dict[str, Any]) -> None:
        """把本次提交的结论落到记录上；重复提交时这里永远是最新一次的内容。"""
        entry["技术等级"] = str(values.get("技术等级") or "").strip()
        entry["评定结论"] = str(values.get("评定结论") or "").strip()
        operator = str(values.get("评定人员") or "").strip()
        if operator:
            entry["评定人员"] = operator
        entry["评定日期"] = str(values.get("评定日期") or "").strip() or datetime.now().date().isoformat()

    @staticmethod
    def _append_history(entry: dict[str, Any], history: list[dict[str, Any]], action: str) -> str:
        """追加本次结论快照；与上一版完全相同的重复提交不再重复留档。"""
        snapshot = {
            "动作": action,
            "技术等级": entry.get("技术等级") or "",
            "评定结论": entry.get("评定结论") or "",
            "评定人员": entry.get("评定人员") or "",
            "记录时间": datetime.now().isoformat(timespec="seconds"),
        }
        comparable = ("动作", "技术等级", "评定结论", "评定人员")
        if history and all(history[-1].get(key) == snapshot[key] for key in comparable):
            return f"评定记录已{action}，与上一版结论一致，保留最新结论不再重复留档"
        history.append(snapshot)
        return f"评定记录已{action}，技术等级更新为「{snapshot['技术等级']}」"
