#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端冒烟验证脚本 (Task C)
按 Antigravity交接说明.md 第 3 节任务 C 检查关键 API 链路
"""
import urllib.request
import urllib.parse
import json
import os
import sys

BASE = "http://127.0.0.1:8787"

def req(path, method="GET", data=None):
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            try:
                return status, json.loads(content)
            except Exception:
                return status, content
    except urllib.error.HTTPError as e:
        err_content = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_content)
        except Exception:
            return e.code, err_content
    except Exception as e:
        return 0, str(e)

results = []

def record(item, passed, detail=""):
    results.append({"item": item, "passed": passed, "detail": detail})
    mark = "✅ PASS" if passed else "❌ FAIL"
    print(f"{mark} | {item} | {detail}")

print("🚀 开始执行任务 C：端到端冒烟验证...")

# 1. GET /api/settings
st, d = req("/api/settings")
if st == 200 and isinstance(d, dict):
    has_keys = "llm" in d and "token_usage" in d and "engine" in d
    record("GET /api/settings", has_keys, f"keys: llm={bool(d.get('llm'))}, token_usage={'token_usage' in d}, engine={'engine' in d}")
else:
    record("GET /api/settings", False, f"status={st}, d={d}")

# 2. POST /api/settings body {"llm_engine_mode":"api"}
st, d = req("/api/settings", method="POST", data={"llm_engine_mode": "api"})
if st == 200:
    st_get, d_get = req("/api/settings")
    mode = (d_get.get("llm") or {}).get("engine_mode") or (d_get.get("engine") or {}).get("preferred")
    record("POST /api/settings (engine_mode=api)", mode == "api", f"get response mode: {mode}")
else:
    record("POST /api/settings (engine_mode=api)", False, f"status={st}, d={d}")

# 3. POST /api/settings/llm-clear
st, d = req("/api/settings/llm-clear", method="POST", data={})
if st == 200:
    st_get, d_get = req("/api/settings")
    configured = (d_get.get("llm") or {}).get("configured")
    record("POST /api/settings/llm-clear", configured is False, f"llm.configured={configured}")
else:
    record("POST /api/settings/llm-clear", False, f"status={st}, d={d}")

# 4. GET /api/scheduler
st, d = req("/api/scheduler")
if st == 200 and isinstance(d, dict):
    has_tasks = "config" in d and "tasks_meta" in d
    tasks_keys = list((d.get("config") or {}).get("tasks", {}).keys())
    record("GET /api/scheduler", has_tasks and len(tasks_keys) > 0, f"tasks={tasks_keys}")
else:
    record("GET /api/scheduler", False, f"status={st}, d={d}")

# 5. POST /api/scheduler/run-now body {"task":"topics"}
st, d = req("/api/scheduler/run-now", method="POST", data={"task": "topics"})
if st == 200 and isinstance(d, dict):
    status_str = d.get("status")
    record("POST /api/scheduler/run-now (task=topics)", status_str in ("started", "already_running", "ok"), f"status={status_str}")
else:
    record("POST /api/scheduler/run-now (task=topics)", False, f"status={st}, d={d}")

# 6. GET /api/production/status
st, d = req("/api/production/status")
if st == 200 and isinstance(d, dict):
    q = d.get("queue", [])
    has_archived = any("archived" in item for item in q) if q else True
    record("GET /api/production/status", "queue" in d, f"queue_len={len(q)}, sample_fields={list(q[0].keys()) if q else 'empty'}")
else:
    record("GET /api/production/status", False, f"status={st}, d={d}")

# 7. DELETE /api/production/<job_id> (测试临时任务创建与安全删除)
tmp_job_id = "test_smoke_temp_job"
tmp_job_dir = f"/Users/xiaowuliao/Projects/自媒体发布agent/jobs/{tmp_job_id}"
tmp_out_dir = f"/Users/xiaowuliao/Projects/自媒体发布agent/outputs/{tmp_job_id}"
os.makedirs(tmp_job_dir, exist_ok=True)
os.makedirs(tmp_out_dir, exist_ok=True)
with open(os.path.join(tmp_job_dir, "state.json"), "w") as f:
    json.dump({"job_id": tmp_job_id, "state": "draft"}, f)

st, d = req(f"/api/production/{tmp_job_id}", method="DELETE")
cleared = (not os.path.exists(tmp_job_dir)) and (not os.path.exists(tmp_out_dir))
record("DELETE /api/production/<temp_job_id>", st == 200 and cleared, f"status={st}, dir_cleared={cleared}")

# 8. GET /api/topics/feedback-report
st, d = req("/api/topics/feedback-report")
if st == 200 and isinstance(d, dict):
    rep_md = (d.get("report") or {}).get("markdown") or d.get("markdown") or ""
    has_table = "权重" in rep_md or "对比" in rep_md or len(rep_md) > 50
    record("GET /api/topics/feedback-report", has_table, f"report_len={len(rep_md)}, has_table={bool(has_table)}")
else:
    record("GET /api/topics/feedback-report", False, f"status={st}, d={d}")

# 9. GET /api/qa/history
st, d = req("/api/qa/history")
if st == 200 and isinstance(d, dict):
    has_fields = "trends" in d or "top_issues" in d or "milestones" in d or "history" in d
    record("GET /api/qa/history", has_fields, f"keys={list(d.keys())}")
else:
    record("GET /api/qa/history", False, f"status={st}, d={d}")

print("\n" + "="*50)
total = len(results)
passed = sum(1 for r in results if r["passed"])
print(f"📊 冒烟测试总计：{total} 项，通过 {passed} 项，失败 {total - passed} 项")
print("="*50)

if passed == total:
    sys.exit(0)
else:
    sys.exit(1)
