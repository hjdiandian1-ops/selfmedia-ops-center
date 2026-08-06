#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周度质量复盘报告（Phase 3 · 质量可度量）
=========================================
聚合 jobs/ 状态机数据 + outputs/ 校验报告 + 发布回收数据，生成质量周报。

统计维度：
1. 生产量：各状态 Job 分布、完成率（到达 publish/recycle 的比例）
2. 质量分：harsh-critic review 评分分布与趋势
3. 打回率：reject_count 分布、平均打回次数
4. 高频失分项：validate_report.json 中 FAIL/WARN 检查码频次排行（归因依据）
5. 发布效果：publish_log 数据汇总与爆款清单

用法：
    python3 scripts/quality_weekly_report.py            # 打印摘要并落盘 jobs/weekly_report/
    python3 scripts/quality_weekly_report.py --json     # 只输出 JSON
"""
import argparse
import glob
import json
import os
from collections import Counter
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
JOBS_DIR = os.path.join(ROOT, "jobs")
OUT_DIR = os.path.join(ROOT, "outputs")


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def collect():
    stats = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "jobs_total": 0, "by_state": Counter(), "reject_total": 0,
        "scores": [], "validate_verdicts": Counter(), "fail_codes": Counter(),
        "published_records": [], "hits": [],
    }

    for sf in glob.glob(os.path.join(JOBS_DIR, "*", "state.json")):
        data = read_json(sf)
        if not data:
            continue
        stats["jobs_total"] += 1
        stats["by_state"][data.get("state", "?")] += 1
        stats["reject_total"] += data.get("reject_count", 0)
        for st, sc in (data.get("scores") or {}).items():
            stats["scores"].append({"job": data["job_id"], "stage": st, "score": sc})

    for vf in glob.glob(os.path.join(OUT_DIR, "*", "validate_report.json")):
        rep = read_json(vf)
        if not rep:
            continue
        stats["validate_verdicts"][rep.get("verdict", "?")] += 1
        for r in rep.get("results", []):
            if r["level"] in ("FAIL", "WARN"):
                stats["fail_codes"][f"{r['level']}:{r['code']}"] += 1

    for lf in glob.glob(os.path.join(JOBS_DIR, "*", "publish_log.json")):
        log = read_json(lf)
        if not log:
            continue
        for r in log.get("records", []):
            rec = dict(r)
            rec["job_id"] = log["job_id"]
            stats["published_records"].append(rec)
            if r.get("hit"):
                stats["hits"].append(rec)

    stats["by_state"] = dict(stats["by_state"])
    stats["validate_verdicts"] = dict(stats["validate_verdicts"])
    stats["fail_codes"] = dict(stats["fail_codes"].most_common(10))
    return stats


def render_md(s):
    done = s["by_state"].get("publish", 0) + s["by_state"].get("recycle", 0)
    avg_score = (sum(x["score"] for x in s["scores"]) / len(s["scores"])) if s["scores"] else 0
    lines = [
        f"# 📊 自媒体运营工厂 · 质量周报（{s['generated_at']}）",
        "",
        "## 1. 生产概览",
        f"- Job 总数：{s['jobs_total']} ｜ 已发布/回收：{done} ｜ 打回总次数：{s['reject_total']}",
        f"- 状态分布：{json.dumps(s['by_state'], ensure_ascii=False)}",
        "",
        "## 2. 质量分",
        f"- harsh-critic 平均分：{avg_score:.1f}（{len(s['scores'])} 次评分）",
    ]
    for x in s["scores"]:
        lines.append(f"  - {x['job']} [{x['stage']}] = {x['score']}")
    lines += [
        "",
        "## 3. 机器校验",
        f"- 判定分布：{json.dumps(s['validate_verdicts'], ensure_ascii=False)}",
        "- 高频失分项（归因重点）:",
    ]
    if s["fail_codes"]:
        for code, n in s["fail_codes"].items():
            lines.append(f"  - {code} × {n}")
    else:
        lines.append("  - 无")
    lines += ["", "## 4. 发布效果"]
    if s["published_records"]:
        for r in s["published_records"]:
            mark = "🔥" if r.get("hit") else "  "
            lines.append(f"- {mark} {r['job_id']} [{r['platform']}] 阅读 {r['reads']} / 赞 {r['likes']} / 互动率 {r.get('engagement', 0):.1%}")
    else:
        lines.append("- 暂无发布回收数据")
    lines += ["", f"- 爆款数：{len(s['hits'])}（应全部已入库 skills/范文库/）", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="周度质量复盘报告")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    s = collect()
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2, default=str))
        return

    md = render_md(s)
    out_dir = os.path.join(JOBS_DIR, "weekly_report")
    os.makedirs(out_dir, exist_ok=True)
    week = datetime.now().strftime("%Y-W%V")
    out_path = os.path.join(out_dir, f"{week}_质量周报.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"\n📁 周报已落盘：{out_path}")


if __name__ == "__main__":
    main()
