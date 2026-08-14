#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爆款周经验包聚合器
==================
读取近 7 天 data/flywheel/breakdowns/*.json，按平台（小红书/抖音/公众号）
聚合高频公式与拆解要点，写入经验库 lessons.json（source=viral_weekly，
同周同平台幂等更新），输出 data/flywheel/viral_weekly_<周>.md，并自动调用
upgrade_agent_docs.py 把经验补丁写入对应 Agent SOP。

用法：
    python3 scripts/aggregate_viral_lessons.py            # 聚合本周并升级 Agent
    python3 scripts/aggregate_viral_lessons.py --json     # 只打印 JSON 摘要
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FLYWHEEL_DIR = os.path.join(ROOT, "data", "flywheel")
LESSONS_FILE = os.path.join(FLYWHEEL_DIR, "lessons.json")
VIRAL_FILE = os.path.join(FLYWHEEL_DIR, "viral_videos.json")
BREAKDOWN_DIR = os.path.join(FLYWHEEL_DIR, "breakdowns")
AGENTS_DIR = os.path.join(ROOT, "agents")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upgrade_agent_docs  # noqa: E402

PLATFORM_APPLY = {
    "小红书": "小红书主编",
    "抖音": "短视频导演",
    "公众号": "公众号主编",
}

PLATFORM_ADVICE = {
    "小红书": "标题对齐热搜词、封面抓点击、正文做成可收藏的清单/教程/避坑，结尾给关注理由。",
    "抖音": "前 3 秒强钩子、高信息密度保完播，结尾引导收藏/关注等深度行为，选题埋搜索词。",
    "公众号": "标题清晰完整、开头尽快给结论，正文要有转发欲的观点与真实案例，并埋长尾搜索关键词。",
}


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def week_key(dt=None):
    dt = dt or datetime.now()
    return dt.strftime("%G-W%V")


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_recent_breakdowns(since_days=7, now=None, breakdown_dir=BREAKDOWN_DIR,
                           viral_path=VIRAL_FILE):
    """返回 [{id, platform, formula, summary, title, mtime}]，仅近 since_days 天。"""
    now = now or datetime.now()
    videos = (read_json(viral_path) or {}).get("videos", [])
    platform_by_id = {v["id"]: v.get("platform", "") for v in videos}
    title_by_id = {v["id"]: v.get("title", "") for v in videos}
    out = []
    for path in sorted(glob.glob(os.path.join(breakdown_dir, "*.json"))):
        vid = os.path.splitext(os.path.basename(path))[0]
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        if (now - mtime).days >= since_days:
            continue
        bd = read_json(path) or {}
        platform = platform_by_id.get(vid, "")
        if platform not in PLATFORM_APPLY:
            continue
        out.append({
            "id": vid,
            "platform": platform,
            "title": bd.get("title") or title_by_id.get(vid, ""),
            "formula": bd.get("formula", ""),
            "summary": bd.get("summary", ""),
            "why_viral": bd.get("why_viral", ""),
            "evidence_level": bd.get("evidence_level", ""),
            "mtime": mtime.strftime("%Y-%m-%d %H:%M"),
        })
    return out


def build_platform_lesson(platform, items, week):
    """按平台生成一条经验（确定性文本，幂等可比较）。"""
    formulas = Counter()
    for it in items:
        for f in re.split(r"[、,，/]", it.get("formula") or ""):
            f = f.strip()
            if f:
                formulas[f] += 1
    top_formulas = "、".join(f"{f}×{n}" for f, n in formulas.most_common(3)) or "暂无明确公式"
    title = f"{platform}爆款经验周包（{week}）"
    conclusion = (
        f"本周拆解 {len(items)} 条{platform}爆款，高频公式：{top_formulas}。"
        f"执行建议：{PLATFORM_ADVICE[platform]}"
    )
    sample_titles = "；".join(it["title"][:30] for it in items[:3] if it.get("title"))
    evidence = (
        f"近7天拆解 {len(items)} 条{platform}爆款（{sample_titles or '—'}）；"
        f"高频公式：{top_formulas}"
    )
    return {
        "title": title,
        "conclusion": conclusion,
        "evidence": evidence,
        "apply_to": PLATFORM_APPLY[platform],
        "source": "viral_weekly",
        "week": week,
    }


def upsert_lessons(lessons_store, new_lessons, now):
    """同周同平台幂等：命中 source=viral_weekly + apply_to 则更新，否则新增。"""
    lessons = lessons_store.setdefault("lessons", [])
    for nl in new_lessons:
        hit = next((l for l in lessons
                    if l.get("source") == "viral_weekly"
                    and l.get("week") == nl["week"]
                    and l.get("apply_to") == nl["apply_to"]), None)
        if hit:
            hit.update({k: v for k, v in nl.items()})
            hit["updated_at"] = now
        else:
            lessons.insert(0, {
                "id": f"lw_{now.replace('-', '').replace(':', '').replace(' ', '')}",
                **nl,
                "applied": False,
                "created_at": now,
                "updated_at": now,
            })
    lessons_store["updated_at"] = now
    return lessons_store


def build_weekly_md(platform_groups, week, now):
    lines = [
        f"# 爆款周经验包（{week}）",
        f"> 生成时间：{now} ｜ 数据范围：近 7 天拆解产物",
        "",
    ]
    for platform, items in platform_groups.items():
        formulas = Counter()
        for it in items:
            for f in re.split(r"[、,，/]", it.get("formula") or ""):
                f = f.strip()
                if f:
                    formulas[f] += 1
        lines += [
            f"## {platform}（{len(items)} 条）",
            f"- 高频公式：{'、'.join(f'{f}×{n}' for f, n in formulas.most_common(5)) or '—'}",
            f"- 执行建议：{PLATFORM_ADVICE[platform]}",
            "",
            "| 标题 | 公式 | 依据级别 | 拆解日期 |",
            "| --- | --- | --- | --- |",
        ]
        for it in items:
            lines.append(
                f"| {it.get('title', '—')[:40]} | {it.get('formula', '—') or '—'} | "
                f"{it.get('evidence_level', '—') or '—'} | {it.get('mtime', '—')} |")
        lines.append("")
    return "\n".join(lines)


def aggregate(flywheel_dir=FLYWHEEL_DIR, agents_dir=AGENTS_DIR,
              since_days=7, now=None):
    now = now or datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    week = week_key(now)
    breakdowns = load_recent_breakdowns(since_days=since_days, now=now,
                                        breakdown_dir=os.path.join(flywheel_dir, "breakdowns"),
                                        viral_path=os.path.join(flywheel_dir, "viral_videos.json"))
    groups = {}
    for it in breakdowns:
        groups.setdefault(it["platform"], []).append(it)

    lessons_store = read_json(os.path.join(flywheel_dir, "lessons.json")) or {"lessons": []}
    new_lessons = [build_platform_lesson(p, items, week) for p, items in groups.items()]
    upsert_lessons(lessons_store, new_lessons, now_str)
    write_json(os.path.join(flywheel_dir, "lessons.json"), lessons_store)

    weekly_md = build_weekly_md(groups, week, now_str)
    weekly_path = os.path.join(flywheel_dir, f"viral_weekly_{week}.md")
    write_text(weekly_path, weekly_md)

    agents_result = upgrade_agent_docs.upgrade_agents(agents_dir, flywheel_dir)
    return {
        "ok": True,
        "week": week,
        "platforms": {p: len(items) for p, items in groups.items()},
        "lessons": len(new_lessons),
        "weekly_report": weekly_path,
        "agents": agents_result.get("agents", []),
        "updated_at": now_str,
    }


def main():
    ap = argparse.ArgumentParser(description="爆款周经验包聚合器")
    ap.add_argument("--flywheel-dir", default=FLYWHEEL_DIR)
    ap.add_argument("--agents-dir", default=AGENTS_DIR)
    ap.add_argument("--since-days", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = aggregate(args.flywheel_dir, args.agents_dir, args.since_days)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"✅ 周经验包 {result['week']}：平台 {result['platforms']}，经验 {result['lessons']} 条，"
              f"升级 Agent SOP {len(result['agents'])} 份")


if __name__ == "__main__":
    main()
