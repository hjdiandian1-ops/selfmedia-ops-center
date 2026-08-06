#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日流水线编排器 (Phase 3 · 无人值守的确定性部分)
==================================================
把「定时生产 / 48h 回收 / 周度复盘」三个定时任务中的确定性环节封装为一键命令，
Agent 定时任务只需调用本脚本，减少人工步骤、保证无人值守可复现。

用法：
    python3 scripts/run_daily_pipeline.py --topics               # 定时生产(8/12/20点)：热点→选题推荐→(可选)自动建 Job
    python3 scripts/run_daily_pipeline.py --topics --auto-select # 决策超时自动选热度第 1 建 Job（对齐 30 分钟无人回复规则）
    python3 scripts/run_daily_pipeline.py --qa outputs/YYYY-MM-DD_主题名/   # 质检链：契约校验 + harsh-critic 机器评分
    python3 scripts/run_daily_pipeline.py --recycle              # 48h 回收(21:30)：扫描发布 ≥48h 且未回收的 Job
    python3 scripts/run_daily_pipeline.py --weekly               # 周度复盘(周日21点)：生成质量周报
    python3 scripts/run_daily_pipeline.py --all                  # topics + recycle + weekly

退出码：0 = 全部成功（含"无待回收项"）；1 = 有失败/有阻塞项。
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

SCRIPTS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.normpath(os.path.join(SCRIPTS, ".."))
JOBS_DIR = os.path.join(ROOT, "jobs")
STATE_ARTIFACT_48H = 48  # 小时


def run(cmd, desc):
    print(f"\n▶ {desc}: {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    return r.returncode == 0


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def job_topic(job_id):
    """从 job_id 与 state.json theme 拼出选题标题。"""
    data = read_json(os.path.join(JOBS_DIR, job_id, "state.json")) or {}
    theme = data.get("theme") or ""
    return theme if theme else job_id


def cmd_topics(args):
    ok = run([sys.executable, os.path.join(SCRIPTS, "fetch_hot_topics.py")], "热点雷达采集")
    if not ok:
        print("⚠️ RSSHub 采集失败，尝试使用最近一次热点雷达 + WebSearch 降级（采编按 SOP 执行）。")
    ok2 = run([sys.executable, os.path.join(SCRIPTS, "suggest_topics.py")], "选题推荐生成")
    if not ok2:
        return False
    if getattr(args, "auto_select", False):
        # 读最新选题推荐，取热度第 1 建 Job（对齐"30 分钟未回复自动选第 1"）
        import glob
        cands = sorted(glob.glob(os.path.join(ROOT, "materials", "*", "*_选题推荐.md")))
        if not cands:
            print("❌ 未找到选题推荐文件，无法自动建 Job")
            return False
        latest = cands[-1]
        topic_line = next((l for l in open(latest, encoding="utf-8") if l.startswith("- 主题方向")), "")
        if not topic_line:
            print("⚠️ 选题推荐无候选，跳过自动建 Job")
            return True
        title = topic_line.split("：", 1)[1].strip() if "：" in topic_line else topic_line.split(":", 1)[1].strip()
        today = datetime.now().strftime("%Y-%m-%d")
        job_id = f"{today}_{title[:12]}"
        r = run([sys.executable, os.path.join(SCRIPTS, "job_state.py"),
                 "init", job_id, "--theme", title], f"自动创建 Job（决策超时默认项）: {title}")
        return r
    return True


def cmd_qa(args):
    out_dir = args.qa
    job_id = os.path.basename(os.path.normpath(out_dir))
    state_data = read_json(os.path.join(JOBS_DIR, job_id, "state.json"))
    if state_data is None:
        print(f"❌ 缺少 {os.path.join(JOBS_DIR, job_id, 'state.json')}：先 job_state.py init <job_id>，再跑质检。")
        return False
    if state_data.get("state") in ("topic", "materials"):
        print(f"❌ 前置产物未就绪：当前状态 {state_data.get('state')}，需先推进到 draft/visual 再质检。")
        return False
    r1 = run([sys.executable, os.path.join(SCRIPTS, "validate_materials_contract.py"), out_dir,
              "--out", os.path.join(out_dir, "validate_report.json")], "素材契约校验")
    r2 = run([sys.executable, os.path.join(SCRIPTS, "harsh_critic_score.py"), out_dir,
              "--out", os.path.join(out_dir, "harsh_report.json")], "Harsh Critic 机器评分")
    r3 = run([sys.executable, os.path.join(SCRIPTS, "generate_score_report.py"), out_dir],
             "评分报告生成（机器初筛版）")
    vr = read_json(os.path.join(out_dir, "validate_report.json")) or {}
    hr = read_json(os.path.join(out_dir, "harsh_report.json")) or {}
    print("-" * 60)
    print(f"📋 质检汇总：contract={vr.get('verdict', '?')}（FAIL {vr.get('fails', '?')}）｜ "
          f"harsh={hr.get('score', '?')}/100 → {hr.get('verdict', '?')}")
    if not (r1 and r2):
        print(f"❌ 质检链有失败项：{out_dir}")
        return False
    if not (r3 and os.path.exists(os.path.join(out_dir, "评分报告.md"))):
        print("❌ 评分报告.md 生成失败，无法定稿。")
        return False
    if vr.get("verdict") == "REJECTED" or hr.get("verdict") == "REJECTED":
        print("🛑 未通过质检门，退回对应主编重写。")
        return False
    # P0：质检通过后自动推进状态机（review → archive）
    score = hr.get("score", 0)
    cur = state_data.get("state")
    if cur in ("draft", "visual"):
        if not run([sys.executable, os.path.join(SCRIPTS, "job_state.py"),
                    "set", job_id, "review", "--score", str(score),
                    "--note", "质检链通过（机器初筛），等待人工复核评分报告"], "推进 review"):
            return False
    if cur in ("draft", "visual", "review"):
        if not run([sys.executable, os.path.join(SCRIPTS, "job_state.py"),
                    "set", job_id, "archive",
                    "--note", "质检链通过且评分报告已落盘，自动归档；发布前仍需人工复核评分报告"], "推进 archive"):
            return False
    return True


def cmd_recycle(_args):
    """扫描发布 ≥48h 且未回收的 Job，输出待回收清单。"""
    due, ok = [], 0
    for d in sorted(os.listdir(JOBS_DIR)):
        sf = os.path.join(JOBS_DIR, d, "state.json")
        data = read_json(sf)
        if not data:
            continue
        if data.get("state") not in ("publish", "archive"):
            continue
        log = read_json(os.path.join(JOBS_DIR, d, "publish_log.json")) or {}
        if log.get("records"):
            continue  # 已有回收记录
        published_at = log.get("published_at") or data.get("updated_at")
        if not published_at:
            continue
        try:
            pt = datetime.strptime(published_at, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        age_h = (datetime.now() - pt).total_seconds() / 3600
        if age_h >= STATE_ARTIFACT_48H:
            due.append((d, job_topic(d), published_at, int(age_h)))
        else:
            ok += 1
    if due:
        print("📊 以下 Job 发布 ≥48h 且未回收，请回填数据：")
        for d, t, pa, age in due:
            print(f"   ⏰ {d} ｜ {t} ｜ 发布 {pa}（{age}h）")
            print(f"      python3 scripts/collect_post_stats.py {d} --platform 小红书 --reads N --likes N ...")
        print(f"\n（另有 {ok} 个 Job 未到 48h 或已回收）")
        return False  # 有阻塞项 → 非零
    print(f"✅ 无 48h 待回收 Job（检查 {len(os.listdir(JOBS_DIR)) if os.path.isdir(JOBS_DIR) else 0} 个 Job）")
    return True


def cmd_weekly(_args):
    return run([sys.executable, os.path.join(SCRIPTS, "quality_weekly_report.py")], "周度质量复盘")


def main():
    ap = argparse.ArgumentParser(description="每日流水线编排器")
    ap.add_argument("--topics", action="store_true", help="热点→选题→(可选)建 Job")
    ap.add_argument("--auto-select", dest="auto_select", action="store_true",
                    help="与 --topics 联用：决策超时自动选热度第 1 建 Job（单独用时等同 --topics --auto-select）")
    ap.add_argument("--qa", metavar="OUTPUT_DIR", help="质检链（契约校验 + 机器评分）")
    ap.add_argument("--recycle", action="store_true", help="48h 回收检查")
    ap.add_argument("--weekly", action="store_true", help="周度质量复盘")
    ap.add_argument("--all", action="store_true", help="topics + recycle + weekly")
    args = ap.parse_args()
    if not (args.topics or args.qa or args.recycle or args.weekly or args.all or args.auto_select):
        ap.error("至少指定一个动作：--topics | --qa | --recycle | --weekly | --all")

    if args.all:
        args.topics = args.recycle = args.weekly = True
        args.auto_select = True
    if args.auto_select and not args.topics:
        args.topics = True  # 单独 --auto-select 视为 topics

    results = []
    if args.topics:
        results.append(("topics" + ("(auto-select)" if args.auto_select else ""), cmd_topics(args)))
    if args.qa:
        results.append(("qa", cmd_qa(args)))
    if args.recycle:
        results.append(("recycle", cmd_recycle(args)))
    if args.weekly:
        results.append(("weekly", cmd_weekly(args)))

    print("\n" + "=" * 60)
    ok_all = all(ok for _, ok in results)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    print(f"总体：{'✅ 全部完成' if ok_all else '❌ 有阻塞项，请人工处理'}（退出码 {'0' if ok_all else '1'}）")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
