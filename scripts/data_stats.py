#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自有数据统计引擎（Phase 3.5 · 不依赖第三方接口）
================================================
统计对象是本仓库自己产生的数据：
  - 发布动作：jobs/*/publish_log.json 的 publish[]（公众号草稿 API 推送、小红书发布）
  - 人工回填：publish_log.json 的 records[]（阅读/赞/藏/评/链接）
  - 内容特征：outputs/<job_id>/ 下排版 HTML 的字数、data-viz 组件数、小红书卡片数
  - 任务状态：jobs/*/state.json

输出：
  data/stats/summary.json       机器可读聚合结果（工作台 /api/stats 直接复用）
  data/stats/数据统计报告.md     人类可读统计报告

用法：
  python3 scripts/data_stats.py collect   # 扫描并生成 summary.json + 报告
  python3 scripts/data_stats.py show      # 只打印 JSON 摘要
  python3 scripts/data_stats.py report    # 只生成 Markdown 报告
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
JOBS_DIR = os.path.join(ROOT, "jobs")
OUTPUTS_DIR = os.path.join(ROOT, "outputs")
DATA_DIR = os.path.join(ROOT, "data", "stats")

PLATFORMS = ("小红书", "公众号", "短视频")
REPORT_FILENAME = "数据统计报告.md"


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


def iter_jobs(jobs_dir):
    """遍历 jobs/ 下所有任务：state.json + publish_log.json。"""
    if not os.path.isdir(jobs_dir):
        return
    for d in sorted(os.listdir(jobs_dir)):
        sf = os.path.join(jobs_dir, d, "state.json")
        state = read_json(sf)
        if not state:
            continue
        yield {
            "job_id": state.get("job_id", d),
            "theme": state.get("theme", ""),
            "state": state.get("state", "?"),
            "scores": state.get("scores", {}),
            "reject_count": state.get("reject_count", 0),
            "created_at": state.get("created_at", ""),
            "updated_at": state.get("updated_at", ""),
            "log": read_json(os.path.join(jobs_dir, d, "publish_log.json")) or {},
        }


def content_features(outputs_dir, job_id):
    """从 outputs/ 提取内容特征（供内容特征分析使用）。"""
    jdir = os.path.join(outputs_dir, job_id)
    feats = {"has_outputs": os.path.isdir(jdir)}
    if not feats["has_outputs"]:
        return feats

    gzh_dir = os.path.join(jdir, "公众号")
    gzh_htmls = [p for p in glob.glob(os.path.join(gzh_dir, "*.html"))
                 if "预览" not in os.path.basename(p)]
    if gzh_htmls:
        gzh = max(gzh_htmls, key=lambda p: os.path.getsize(p))
        html = read_text(gzh)
        text = re.sub(r"<[^>]+>", "", html)
        feats["gzh_word_count"] = len(re.sub(r"\s+", "", text))
        feats["gzh_viz_count"] = len(re.findall(r'data-viz\s*=\s*"[^"]+"', html))
        feats["gzh_unresolved_img"] = "[[IMG:" in html

    xhs_dir = os.path.join(jdir, "小红书")
    if os.path.isdir(xhs_dir):
        imgs = [n for n in os.listdir(xhs_dir)
                if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
        feats["xhs_images"] = len(imgs)
        slides = sorted(glob.glob(os.path.join(xhs_dir, "*slides.html"))
                        + glob.glob(os.path.join(xhs_dir, "*.html")))
        if slides:
            feats["xhs_has_viz"] = bool(
                re.search(r"h-bar-chart|bar-tower|data-viz", read_text(slides[0])))
    return feats


def build_events(jobs_dir, outputs_dir):
    """把仓库内的发布动作/回填记录统一成事件流（自有统计的事实来源）。"""
    events = []
    for job in iter_jobs(jobs_dir):
        jid, theme = job["job_id"], job["theme"]
        title = job["log"].get("title") or theme or jid
        feats = content_features(outputs_dir, jid)

        if job.get("created_at"):
            events.append({
                "id": f"{jid}|job_created|{job['created_at']}",
                "type": "job_created", "job_id": jid, "title": title, "theme": theme,
                "platform": "", "at": job["created_at"], "features": feats,
            })

        for pub in job["log"].get("publish", []):
            if pub.get("status") == "failed":
                continue
            at = pub.get("at") or job["log"].get("published_at") or ""
            events.append({
                "id": f"{jid}|publish|{at}|{pub.get('platform', '')}",
                "type": "publish", "job_id": jid, "title": title, "theme": theme,
                "platform": pub.get("platform", ""), "at": at,
                "mode": pub.get("mode", ""), "draft_media_id": pub.get("draft_media_id", ""),
                "features": feats,
            })

        for rec in job["log"].get("records", []):
            at = rec.get("collected_at", "")
            events.append({
                "id": f"{jid}|metric|{at}|{rec.get('platform', '')}",
                "type": "metric", "job_id": jid, "title": title, "theme": theme,
                "platform": rec.get("platform", ""), "at": at,
                "reads": rec.get("reads", 0), "likes": rec.get("likes", 0),
                "collects": rec.get("collects", 0), "comments": rec.get("comments", 0),
                "engagement": rec.get("engagement", 0.0), "hit": bool(rec.get("hit")),
                "url": rec.get("url", ""), "features": feats,
            })
    return events


def _engagement(reads, likes, collects, comments):
    return round((likes + collects + comments) / reads, 4) if reads > 0 else 0.0


def aggregate(events, jobs_dir, outputs_dir):
    """事件流 → 聚合统计（KPI / 平台 / 主题 / 趋势 / 内容特征 / 数据口径）。"""
    jobs = list(iter_jobs(jobs_dir))
    by_state = Counter(j["state"] for j in jobs)
    scores = [sc for j in jobs for sc in (j["scores"] or {}).values()]

    pubs = [e for e in events if e["type"] == "publish"]
    metrics = [e for e in events if e["type"] == "metric"]

    total_reads = sum(e["reads"] for e in metrics)
    total_likes = sum(e["likes"] for e in metrics)
    total_collects = sum(e["collects"] for e in metrics)
    total_comments = sum(e["comments"] for e in metrics)
    hits = [e for e in metrics if e["hit"]]

    published_jobs = sum(1 for j in jobs if j["log"].get("publish") or j["log"].get("records"))

    # 待回收：publish/archive 态 + 有发布记录 + 无回填 + 距今 ≥48h
    pending_recycle = 0
    for j in jobs:
        log = j["log"]
        if log.get("records"):
            continue
        if j["state"] not in ("publish", "archive"):
            continue
        pt = log.get("published_at")
        try:
            age_h = (datetime.now() - datetime.strptime(pt, "%Y-%m-%d %H:%M:%S")).total_seconds() / 3600
            if age_h >= 48:
                pending_recycle += 1
        except Exception:
            pass

    # 平台对比
    by_platform = []
    for platform in PLATFORMS:
        pe = [e for e in pubs if e["platform"] == platform]
        me = [e for e in metrics if e["platform"] == platform]
        p_reads = sum(e["reads"] for e in me)
        by_platform.append({
            "platform": platform,
            "publish_events": len(pe),
            "posts": len({e["job_id"] for e in pe + me}),
            "backfills": len(me),
            "reads": p_reads,
            "likes": sum(e["likes"] for e in me),
            "collects": sum(e["collects"] for e in me),
            "comments": sum(e["comments"] for e in me),
            "engagement": _engagement(
                p_reads,
                sum(e["likes"] for e in me),
                sum(e["collects"] for e in me),
                sum(e["comments"] for e in me)),
            "hits": sum(1 for e in me if e["hit"]),
        })

    # 主题表现
    theme_map = defaultdict(lambda: {
        "posts": set(), "publish_events": 0, "backfills": 0,
        "reads": 0, "likes": 0, "collects": 0, "comments": 0, "hits": 0})
    for e in events:
        if not e["theme"]:
            continue
        t = theme_map[e["theme"]]
        if e["type"] == "publish":
            t["posts"].add(e["job_id"])
            t["publish_events"] += 1
        elif e["type"] == "metric":
            t["posts"].add(e["job_id"])
            t["backfills"] += 1
            t["reads"] += e["reads"]
            t["likes"] += e["likes"]
            t["collects"] += e["collects"]
            t["comments"] += e["comments"]
            if e["hit"]:
                t["hits"] += 1
    by_theme = []
    for theme, t in sorted(theme_map.items(), key=lambda kv: -kv[1]["reads"]):
        if not t["posts"]:
            continue  # 只展示有发布/回填事件的主题
        item = dict(t)
        item["posts"] = len(item["posts"])
        item["engagement"] = _engagement(
            item["reads"], item["likes"], item["collects"], item["comments"])
        by_theme.append({"theme": theme, **item})

    # 近 7 天趋势（发布动作按天，阅读/爆款按回填时间）
    today = datetime.now().date()
    trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        ds = day.isoformat()
        pe = [e for e in pubs if (e["at"] or "")[:10] == ds]
        me = [e for e in metrics if (e["at"] or "")[:10] == ds]
        trend.append({
            "date": ds,
            "label": day.strftime("%m-%d"),
            "publish_count": len(pe),
            "count": len(me),
            "reads": sum(e["reads"] for e in me),
            "hits": sum(1 for e in me if e["hit"]),
        })

    # 最近回填（前端表格兼容旧字段）
    recent = sorted(metrics, key=lambda e: e["at"], reverse=True)[:20]
    recent = [{
        "job_id": e["job_id"], "theme": e["theme"], "platform": e["platform"],
        "collected_at": e["at"],
        "reads": e["reads"], "likes": e["likes"], "collects": e["collects"],
        "comments": e["comments"], "engagement": e["engagement"],
        "hit": e["hit"], "url": e["url"],
    } for e in recent]

    # 最佳表现
    def best_rows(evs, key, limit=5):
        rows = sorted([e for e in evs if e.get("reads", 0) > 0], key=key, reverse=True)[:limit]
        return [{
            "job_id": e["job_id"], "title": e["title"], "theme": e["theme"],
            "platform": e["platform"], "collected_at": e["at"],
            "reads": e["reads"], "likes": e["likes"], "collects": e["collects"],
            "comments": e["comments"], "engagement": e["engagement"], "hit": e["hit"],
        } for e in rows]

    best = {
        "by_reads": best_rows(metrics, lambda e: e["reads"]),
        "by_engagement": best_rows(metrics, lambda e: e["engagement"]),
        "hits": best_rows(hits, lambda e: e["reads"], limit=10),
    }

    # 内容特征分析（样本少时仅供参考）
    def bucket_stats(evs, bucket_fn):
        groups = defaultdict(list)
        for e in evs:
            groups[bucket_fn(e)].append(e)
        out = []
        for label, items in groups.items():
            reads = sum(x["reads"] for x in items)
            out.append({
                "bucket": label,
                "n": len(items),
                "avg_reads": round(reads / len(items), 1) if items else 0,
                "avg_engagement": round(
                    sum(x["engagement"] for x in items) / len(items), 4) if items else 0.0,
                "hits": sum(1 for x in items if x["hit"]),
            })
        out.sort(key=lambda x: -x["avg_reads"])
        return out

    content_insights = {
        "title_number": bucket_stats(
            metrics,
            lambda e: "标题含数字" if re.search(r"\d", e["title"] or "") else "标题不含数字"),
        "gzh_viz": bucket_stats(
            metrics,
            lambda e: "≥2 个图表"
            if (e["features"].get("gzh_viz_count") or 0) >= 2
            else ("1 个图表" if e["features"].get("gzh_viz_count") else "无公众号 HTML")),
        "xhs_cards": bucket_stats(
            metrics,
            lambda e: "≥4 张卡片"
            if (e["features"].get("xhs_images") or 0) >= 4
            else ("1-3 张卡片" if e["features"].get("xhs_images") else "无卡片")),
        "note": "样本量不足时仅供参考；累计 4-8 周真实数据后再反哺选题与标题公式。",
    }

    # 数据来源口径
    untracked = []
    for j in jobs:
        if j["log"].get("publish") and not j["log"].get("records"):
            untracked.append({
                "job_id": j["job_id"],
                "title": j["log"].get("title") or j["theme"] or j["job_id"],
                "published_at": j["log"].get("published_at", ""),
            })
    untracked.sort(key=lambda u: u["published_at"], reverse=True)
    data_status = {
        "auto_tracked": len(pubs),
        "manual_backfill": len(metrics),
        "untracked_posts": len(untracked),
        "untracked_list": untracked[:10],
        "pending_recycle": pending_recycle,
        "external_note": "公众号 datacube 未开通权限、小红书无官方开放 API；"
                         "当前数据 = 仓库内发布动作（自动） + 人工回填（手动），不依赖第三方抓取。",
    }

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "jobs_total": len(jobs),
        "by_state": dict(by_state),
        "reject_total": sum(j["reject_count"] for j in jobs),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "score_count": len(scores),
        "published_jobs": published_jobs,
        "publish_events": len(pubs),
        "backfill_records": len(metrics),
        "pending_recycle": pending_recycle,
        "hits": len(hits),
        "total_reads": total_reads,
        "total_likes": total_likes,
        "total_collects": total_collects,
        "total_comments": total_comments,
        "avg_engagement": _engagement(total_reads, total_likes, total_collects, total_comments),
        "recent": recent,
        "trend": trend,
        "by_platform": by_platform,
        "by_theme": by_theme,
        "best": best,
        "content_insights": content_insights,
        "data_status": data_status,
        "report_path": f"data/stats/{REPORT_FILENAME}",
    }


def build_summary(jobs_dir=JOBS_DIR, outputs_dir=OUTPUTS_DIR):
    """实时聚合（工作台 /api/stats 直接调用）。"""
    events = build_events(jobs_dir, outputs_dir)
    return aggregate(events, jobs_dir, outputs_dir)


def render_markdown(s):
    lines = [
        f"# 📊 自有数据统计报告（{s['generated_at']}）",
        "",
        "## 1. 大盘",
        f"- 任务总数：{s['jobs_total']} ｜ 已发布任务：{s['published_jobs']} ｜ 发布动作：{s['publish_events']} 次",
        f"- 人工回填：{s['backfill_records']} 条 ｜ 总阅读：{s['total_reads']} ｜ 总赞：{s['total_likes']} ｜ 总藏：{s['total_collects']} ｜ 总评：{s['total_comments']}",
        f"- 平均互动率：{s['avg_engagement']:.2%} ｜ 爆款：{s['hits']} ｜ 待回收：{s['pending_recycle']}",
        f"- 数据来源：发布动作（自动记录 {s['data_status']['auto_tracked']} 次）+ 人工回填（{s['data_status']['manual_backfill']} 条）",
        "",
        "## 2. 平台对比",
    ]
    for p in s["by_platform"]:
        lines.append(
            f"- {p['platform']}：发布 {p['publish_events']} 次 ｜ 回填 {p['backfills']} 条 ｜ "
            f"阅读 {p['reads']} ｜ 互动率 {p['engagement']:.2%} ｜ 爆款 {p['hits']}")
    lines += ["", "## 3. 主题表现"]
    if s["by_theme"]:
        for t in s["by_theme"]:
            lines.append(
                f"- {t['theme']}：发文 {t['posts']} ｜ 回填 {t['backfills']} ｜ "
                f"阅读 {t['reads']} ｜ 互动率 {t['engagement']:.2%} ｜ 爆款 {t['hits']}")
    else:
        lines.append("- 暂无主题数据")
    lines += ["", "## 4. 内容特征分析（样本少时仅供参考）"]
    for label, key in (("标题", "title_number"), ("公众号图表", "gzh_viz"), ("小红书卡片", "xhs_cards")):
        lines.append(f"### {label}")
        for r in s["content_insights"][key]:
            lines.append(
                f"- {r['bucket']}：样本 {r['n']} ｜ 均阅读 {r['avg_reads']} ｜ "
                f"均互动率 {r['avg_engagement']:.2%} ｜ 爆款 {r['hits']}")
    lines += ["", "## 5. 最近回填", ""]
    if s["recent"]:
        for r in s["recent"]:
            mark = "🔥" if r["hit"] else "  "
            lines.append(
                f"- {mark} {r['collected_at']} {r['job_id']} [{r['platform']}] "
                f"阅读 {r['reads']} / 赞 {r['likes']} / 藏 {r['collects']} / 评 {r['comments']} "
                f"互动率 {r['engagement']:.1%}")
    else:
        lines.append("- 暂无回填数据")
    return "\n".join(lines)


def save_summary(root=ROOT, summary=None):
    data_dir = os.path.join(root, "data", "stats")
    os.makedirs(data_dir, exist_ok=True)
    s = summary or build_summary()
    path = os.path.join(data_dir, "summary.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    return path


def write_report(root=ROOT, summary=None):
    data_dir = os.path.join(root, "data", "stats")
    os.makedirs(data_dir, exist_ok=True)
    s = summary or build_summary()
    path = os.path.join(data_dir, REPORT_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_markdown(s))
    return path


def main():
    ap = argparse.ArgumentParser(description="自有数据统计引擎")
    ap.add_argument("cmd", choices=["collect", "show", "report"])
    args = ap.parse_args()

    if args.cmd == "collect":
        s = build_summary()
        p1 = save_summary(summary=s)
        p2 = write_report(summary=s)
        print(f"✅ 统计完成：{p1}")
        print(f"📄 报告：{p2}")
        print(json.dumps({
            "jobs_total": s["jobs_total"],
            "publish_events": s["publish_events"],
            "backfill_records": s["backfill_records"],
            "hits": s["hits"],
            "total_reads": s["total_reads"],
        }, ensure_ascii=False, indent=2))
    elif args.cmd == "show":
        print(json.dumps(build_summary(), ensure_ascii=False, indent=2))
    else:
        print(render_markdown(build_summary()))


if __name__ == "__main__":
    main()
