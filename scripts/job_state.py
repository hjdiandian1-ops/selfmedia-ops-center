#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Job 状态机（自媒体运营工厂 · 断点续跑核心）
============================================
每个选题一个 Job，状态持久化在 jobs/<job_id>/state.json。
任何环节失败可从断点恢复，不必重跑全流程。

状态流转（8 态）：
    topic → materials → draft → visual → review → archive → publish → recycle

用法：
    python3 scripts/job_state.py init  2026-08-04_主题名 --theme "主题描述"
    python3 scripts/job_state.py set   2026-08-04_主题名 draft --score 88 --note "小红书已过审"
    python3 scripts/job_state.py show  2026-08-04_主题名
    python3 scripts/job_state.py list
    python3 scripts/job_state.py auto-advance 2026-08-04_主题名  # 决策超时自动推进
    python3 scripts/job_state.py reject 2026-08-04_主题名 --note "素材衰减，退回重写"
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

STATES = ["topic", "materials", "draft", "visual", "review", "archive", "publish", "recycle"]
JOBS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jobs"))

# 每个状态对应的产物位置（供断点续跑时核对）
STATE_ARTIFACTS = {
    "topic": "对话内选题大纲",
    "materials": "materials/YYYY-MM/<job_id>素材包.md",
    "draft": "outputs/<job_id>/{平台}/文案.md（带 frontmatter 契约）",
    "visual": "outputs/<job_id>/小红书/视觉卡片.html + 封面.png",
    "review": "outputs/<job_id>/评分报告.md（harsh-critic v2）",
    "archive": "outputs/<job_id>/ 三级目录归档 + 临时文件清扫",
    "publish": "publish_log.json（发布记录）",
    "recycle": "发布 48h 数据回收记录",
}


def state_path(job_id):
    return os.path.join(JOBS_DIR, job_id, "state.json")


def load(job_id):
    p = state_path(job_id)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save(job_id, data):
    os.makedirs(os.path.dirname(state_path(job_id)), exist_ok=True)
    with open(state_path(job_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fmt_remaining(deadline):
    """决策截止剩余时间(人类可读)。"""
    d = datetime.strptime(deadline, "%Y-%m-%d %H:%M:%S")
    secs = (d - datetime.now()).total_seconds()
    if secs <= 0:
        return "已到期"
    return f"{int(secs // 60)} 分 {int(secs % 60)} 秒"


def cmd_init(args):
    if load(args.job_id):
        print(f"⚠️ Job 已存在：{args.job_id}（用 show 查看，或换 job_id）")
        sys.exit(1)
    data = {
        "job_id": args.job_id,
        "theme": args.theme or "",
        "state": "topic",
        "created_at": now(),
        "updated_at": now(),
        "decision_deadline": (datetime.now() + timedelta(minutes=args.deadline_minutes)).strftime("%Y-%m-%d %H:%M:%S"),
        "history": [{"state": "topic", "at": now(), "note": "Job 创建"}],
        "reject_count": 0,
        "scores": {},
    }
    save(args.job_id, data)
    print(f"✅ Job 已创建：{args.job_id} → 状态 topic")
    print(f"   状态文件：{state_path(args.job_id)}")


def cmd_set(args):
    data = load(args.job_id)
    if not data:
        print(f"❌ Job 不存在：{args.job_id}（先 init）")
        sys.exit(1)
    target = args.state
    cur_idx = STATES.index(data["state"])
    tgt_idx = STATES.index(target)
    if tgt_idx < cur_idx:
        print(f"⚠️ 状态回退：{data['state']} → {target}（打回重写场景）")
    elif tgt_idx > cur_idx + 1:
        skipped = STATES[cur_idx + 1:tgt_idx]
        print(f"⚠️ 跳过中间状态 {skipped}，请确认这些环节产物已就绪：")
        for s in skipped:
            print(f"   - {s}: {STATE_ARTIFACTS[s]}")
    data["state"] = target
    data["updated_at"] = now()
    entry = {"state": target, "at": now()}
    if args.note:
        entry["note"] = args.note
    if args.score is not None:
        data["scores"][target] = args.score
        entry["score"] = args.score
    data["history"].append(entry)
    save(args.job_id, data)
    print(f"✅ {args.job_id} → {target}" + (f"（score={args.score}）" if args.score is not None else ""))


def cmd_reject(args):
    data = load(args.job_id)
    if not data:
        print(f"❌ Job 不存在：{args.job_id}")
        sys.exit(1)
    data["reject_count"] = data.get("reject_count", 0) + 1
    data["state"] = "draft"  # 打回创作环节
    data["updated_at"] = now()
    data["history"].append({"state": "draft", "at": now(),
                            "note": f"REJECTED 第 {data['reject_count']} 次：{args.note or ''}"})
    save(args.job_id, data)
    print(f"🔴 已打回 draft（第 {data['reject_count']} 次）")
    if data["reject_count"] >= 2:
        print("🛑 连续 2 次 REJECTED——按铁律停止自动打回，请用户人工仲裁后再继续。")
        sys.exit(2)


def cmd_show(args):
    data = load(args.job_id)
    if not data:
        print(f"❌ Job 不存在：{args.job_id}")
        sys.exit(1)
    idx = STATES.index(data["state"])
    progress = " ".join(f"[{s}]" if i == idx else (f"({s})" if i < idx else s) for i, s in enumerate(STATES))
    print(f"📋 Job: {data['job_id']}  主题: {data.get('theme', '')}")
    print(f"   进度: {progress}")
    print(f"   打回次数: {data.get('reject_count', 0)}  更新于: {data['updated_at']}")
    if data.get("decision_deadline"):
        dd = data["decision_deadline"]
        mark = "（⏰ 已超时，auto-advance 将自动推进）" if now() >= dd else f"（剩余 {fmt_remaining(dd)}）"
        print(f"   决策截止: {dd} {mark}")
    if data.get("scores"):
        print(f"   评分: {data['scores']}")
    nxt = STATES[idx + 1] if idx + 1 < len(STATES) else None
    if nxt:
        print(f"   下一环节: {nxt} → 产物要求: {STATE_ARTIFACTS[nxt]}")
    print("   最近历史:")
    for h in data["history"][-5:]:
        line = f"   - {h['at']}  {h['state']}"
        if h.get("score") is not None:
            line += f"  score={h['score']}"
        if h.get("note"):
            line += f"  # {h['note']}"
        print(line)


def cmd_auto_advance(args):
    """决策超时自动推进:用户 30 分钟(或 --deadline-minutes)未回复决策时,自动推进到下一状态。
    未到截止时间则不推进(退出码 1),由定时任务感知"继续等待"。
    """
    data = load(args.job_id)
    if not data:
        print(f"❌ Job 不存在：{args.job_id}")
        sys.exit(1)
    deadline = data.get("decision_deadline")
    if not deadline:
        print("⚠️ 该 Job 未设置决策截止时间(init 时 --deadline-minutes),跳过自动推进")
        sys.exit(1)
    now_s = now()
    if now_s < deadline:
        print(f"⏳ 决策窗口未到：剩余 {fmt_remaining(deadline)}，用户仍可介入（{data['state']}）")
        sys.exit(1)
    cur = data["state"]
    cur_idx = STATES.index(cur)
    if cur_idx >= len(STATES) - 1:
        print(f"✅ 已是终态 {cur}，无需推进")
        return
    nxt = STATES[cur_idx + 1]
    data["state"] = nxt
    data["updated_at"] = now_s
    data["history"].append({"state": nxt, "at": now_s, "note": "决策超时自动推进(用户未回复，选默认项)"})
    save(args.job_id, data)
    print(f"⏭️ 决策超时，自动推进：{cur} → {nxt}（默认项）")


def cmd_list(_args):
    if not os.path.isdir(JOBS_DIR):
        print("（jobs/ 目录为空）")
        return
    rows = []
    for d in sorted(os.listdir(JOBS_DIR)):
        data = load(d)
        if data:
            rows.append((d, data["state"], data.get("reject_count", 0), data["updated_at"]))
    if not rows:
        print("（暂无 Job）")
        return
    print(f"{'JOB_ID':<40} {'状态':<10} {'打回':<4} 更新时间")
    for r in rows:
        print(f"{r[0]:<40} {r[1]:<10} {r[2]:<4} {r[3]}")


def main():
    ap = argparse.ArgumentParser(description="Job 状态机")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("job_id")
    p.add_argument("--theme", default="")
    p.add_argument("--deadline-minutes", type=int, default=30,
                   help="选题决策超时(分钟)，超时后 auto-advance 自动选默认项（默认 30）")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("set")
    p.add_argument("job_id")
    p.add_argument("state", choices=STATES)
    p.add_argument("--score", type=int)
    p.add_argument("--note", default="")
    p.set_defaults(fn=cmd_set)

    p = sub.add_parser("reject")
    p.add_argument("job_id")
    p.add_argument("--note", default="")
    p.set_defaults(fn=cmd_reject)

    p = sub.add_parser("show")
    p.add_argument("job_id")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("list")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("auto-advance")
    p.add_argument("job_id")
    p.set_defaults(fn=cmd_auto_advance)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
