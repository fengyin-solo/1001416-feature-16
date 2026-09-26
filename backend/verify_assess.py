"""技术评定落稳链路验证：状态流转、结论落库、历史留存、快照持久化与回退拦截。"""
import os
import tempfile

tmp = tempfile.mkdtemp()
os.environ["APP_STORE_FILE"] = os.path.join(tmp, "store.json")

from fastapi.testclient import TestClient

from app.main import app
from app.store import store

client = TestClient(app)


def get(eid):
    return client.get(f"/api/assess/{eid}").json()


# 1. 既有数据迁移：历史结论补齐、评定状态与工作流状态同步
e2 = get(2)
assert e2["评定状态"] == "评定中", e2
assert len(e2["history"]) == 1 and e2["history"][0]["动作"] == "历史结论", e2["history"]
print("1. 既有历史结论可读:", e2["history"][0]["评定结论"])

# 2. 确认定级：等级与结论随动作落库，详情/列表同步
r = client.post("/api/assess/2/actions", json={"values": {
    "action": "确认定级", "技术等级": "二类", "评定结论": "结构良好，二类", "评定人员": "张三", "评定日期": "2026-09-26",
}}).json()
assert r["ok"] is True, r
e2 = get(2)
assert e2["技术等级"] == "二类" and e2["评定结论"] == "结构良好，二类"
assert e2["status"] == "已定级" and e2["评定状态"] == "已定级" and e2["pending"] is True
listed = [x for x in client.get("/api/assess").json()["items"] if x["id"] == 2][0]
assert listed["技术等级"] == "二类", listed
overview = client.get("/api/overview").json()
assess_stat = [m for m in overview["modules"] if m["name"] == "assess"][0]
print("2. 定级落库: 详情/列表等级=", e2["技术等级"], "概览待处理=", assess_stat["pending"])

# 3. 结论为空：保留原等级，并说明是哪一项不合规
r = client.post("/api/assess/2/actions", json={"values": {"action": "确认定级", "技术等级": "三类", "评定结论": "   "}}).json()
assert r["ok"] is False and "评定结论不能为空" in r["message"], r
e2 = get(2)
assert e2["技术等级"] == "二类", e2
print("3. 空结论拦截:", r["message"])

# 4. 连续两次提交：以最新结论为准，旧结论保留在历史里
for grade, note in [("三类", "复测降为三类"), ("四类", "再次复测降为四类")]:
    r = client.post("/api/assess/2/actions", json={"values": {
        "action": "确认定级", "技术等级": grade, "评定结论": note, "评定人员": "李四", "评定日期": "2026-09-26",
    }}).json()
    assert r["ok"] is True, r
e2 = get(2)
assert e2["技术等级"] == "四类" and e2["评定结论"] == "再次复测降为四类", e2
actions = [h["动作"] for h in e2["history"]]
assert actions == ["历史结论", "确认定级", "确认定级", "确认定级"], actions
print("4. 重复提交最新生效:", e2["技术等级"], "历史条数=", len(e2["history"]))

# 5. 发起复评后不能回退到评定中
r = client.post("/api/assess/2/actions", json={"values": {
    "action": "发起复评", "技术等级": "三类", "评定结论": "复评结论：三类",
}}).json()
assert r["ok"] is True and get(2)["status"] == "已复评" and get(2)["pending"] is False
r = client.post("/api/assess/2/actions", json={"values": {"action": "开始评定"}}).json()
assert r["ok"] is False and "不能回退到评定中" in r["message"], r
r = client.post("/api/assess/2/actions", json={"values": {"action": "确认定级", "技术等级": "二类", "评定结论": "x"}}).json()
assert r["ok"] is False and "不能回退到已定级" in r["message"], r
print("5. 已复评禁止回退:", r["message"])

# 6. 快照落盘 + 重启恢复：新 Store 从同一文件读取，结论不回档
assert os.path.exists(store._store_file)
from app.store import Store
restarted = Store()
row = next(x for x in restarted.rows("assess") if x["id"] == 2)
assert row["技术等级"] == "三类" and row["status"] == "已复评", row
assert len(row["history"]) == 5, row["history"]
assert [h["动作"] for h in row["history"]] == ["历史结论", "确认定级", "确认定级", "确认定级", "发起复评"]
print("6. 重启恢复: 等级=", row["技术等级"], "状态=", row["status"], "历史=", len(row["history"]))

print("\n全部验证通过 ✅")
