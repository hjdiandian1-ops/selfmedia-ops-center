#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书式数据分析聚合 + 薄弱点诊断
================================
把四页签看板导出（data/stats/dashboard/*.json）与笔记明细
（data/stats/xhs_notes.json）聚合成「观看/互动/涨粉/发布」四个页签，
并按规则引擎给出薄弱点与提升方向（供工作台 /api/dashboard 使用）。

阈值集中在下方常量，后续调参只改这里。
"""
import json
import os
import re
from datetime import datetime, timedelta

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_DATA_DIR = os.path.join(ROOT, "data", "stats")
DEFAULT_JOBS_DIR = os.path.join(ROOT, "jobs")
DEFAULT_OUTPUTS_DIR = os.path.join(ROOT, "outputs")

# ---------- 薄弱点阈值（可调常量） ----------
CTR_WEAK_PCT = 10.0            # 封面点击率 <10% → 封面/标题弱
ENGAGEMENT_WEAK = 0.01         # 互动率 <1% → 内容价值/引导弱
ENGAGEMENT_DROP_RATIO = 0.2    # 互动率环比下降超过 20% → 提示
COMPLETION_WEAK_PCT = 30.0     # 视频完播率 <30% → 开头钩子弱
FOLLOWER_RATE_WEAK = 0.001     # 涨粉率 <0.1% → 关注引导弱
PUBLISH_GAP_DAYS = 2           # 空窗 ≥2 天 → 更新节奏问题
VIDEO_SHARE_WEAK = 0.2         # 视频占比 <20% → 体裁结构失衡

KINDS = ("publish", "watch", "interact", "follower")


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def iso_date(val):
    s = str(val or "").strip()
    m = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日", s)
    if m:
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    m2 = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m2:
        y, mo, d = m2.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return s


def _num(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _pct_num(v):
    """把 23.2 / 23.2% / 0.232 统一成百分比数值。"""
    v = _num(v, None)
    if v is None:
        return None
    s = str(v)
    if isinstance(v, float) and v <= 1 and not s.endswith("%") and v != 0:
        # 0.232 视为 23.2%（导出通常是百分比数值，保险起见仅对 <1 且原始值非整十的情况转换）
        return round(v * 100, 2)
    return round(v, 2)


def _last_n_days(n):
    today = datetime.now().date()
    return [(today - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def _window_sums(series, days):
    """series: [{date, value}]；返回 (当前窗口合计, 上一窗口合计, 当前逐日 dict)。"""
    days_now = _last_n_days(days)
    days_prev = _last_n_days(days * 2)[:days]
    cur = {}
    prev = {}
    for item in series or []:
        d = iso_date(item.get("date", ""))
        v = _num(item.get("value"))
        if d in days_now:
            cur[d] = v
        elif d in days_prev:
            prev[d] = v
    for d in days_now:
        cur.setdefault(d, 0)
    for d in days_prev:
        prev.setdefault(d, 0)
    return sum(cur.values()), sum(prev.values()), cur


def _notes_list(data_dir):
    store = read_json(os.path.join(data_dir, "xhs_notes.json")) or {}
    return list((store.get("notes") or {}).values())


def _note_window(note, days):
    d = iso_date(note.get("first_published_at", ""))
    return d[:10] in _last_n_days(days)


def _engagement(reads, likes, collects, comments):
    return round((likes + collects + comments) / reads, 4) if reads > 0 else 0.0


def build_tabs(range_days, data_dir):
    dash_dir = os.path.join(data_dir, "dashboard")
    loaded = {k: read_json(os.path.join(dash_dir, f"{k}.json")) or {} for k in KINDS}
    notes = _notes_list(data_dir)
    notes_cur = [n for n in notes if _note_window(n, range_days)]
    account = read_json(os.path.join(data_dir, "xhs_account.json")) or {}

    def nsum(key):
        return sum(_num(n.get(key)) for n in notes_cur)

    def navg(key):
        vals = [_num(n.get(key)) for n in notes_cur if n.get(key) not in (None, "", 0)]
        return round(sum(vals) / len(vals), 1) if vals else None

    # ---------- 发布 ----------
    pub = loaded["publish"]
    pub_acct = pub.get("account") or {}
    total_s, prev_total_s, total_cur = _window_sums(
        (pub.get("series") or {}).get("总发布趋势", []), range_days)
    video_s, prev_video_s, video_cur = _window_sums(
        (pub.get("series") or {}).get("发布视频趋势", []), range_days)
    image_s, prev_image_s, image_cur = _window_sums(
        (pub.get("series") or {}).get("发布图文趋势", []), range_days)
    trend = []
    for d in _last_n_days(range_days):
        trend.append({
            "date": d, "label": d[5:],
            "total": total_cur.get(d, 0), "video": video_cur.get(d, 0),
            "image": image_cur.get(d, 0),
        })
    publish = {
        "kpis": [
            {"key": "总发布", "value": total_s,
             "delta": _delta(total_s, prev_total_s)},
            {"key": "发布视频", "value": video_s,
             "delta": _delta(video_s, prev_video_s)},
            {"key": "发布图文", "value": image_s,
             "delta": _delta(image_s, prev_image_s)},
        ],
        "trend": trend,
        "current_total": total_s,
        "prev_total": prev_total_s,
        "account": {
            "总发布": _num(pub_acct.get("总发布")),
            "发布视频": _num(pub_acct.get("发布视频")),
            "发布图文": _num(pub_acct.get("发布图文")),
            "总发布环比(%)": pub_acct.get("总发布环比(%)"),
        },
    }

    # ---------- 观看 ----------
    watch = loaded["watch"]
    watch_acct = watch.get("account") or {}
    watch_s, prev_watch_s, watch_cur = _window_sums(
        _first_series(watch), range_days)
    exposure = nsum("exposure")
    reads = watch_s if watch_s > 0 else nsum("reads")
    ctr = _pct_num(watch_acct.get("封面点击率"))
    if ctr is None:
        # 笔记明细加权点击率
        exp_sum = sum(_num(n.get("exposure")) for n in notes_cur)
        prod = sum(_num(n.get("ctr")) * _num(n.get("exposure")) for n in notes_cur)
        ctr = round(prod / exp_sum, 2) if exp_sum else None
    watch_trend = [{"date": d, "label": d[5:], "value": watch_cur.get(d, 0)}
                   for d in _last_n_days(range_days)]
    if not any(t["value"] for t in watch_trend):
        # 回退：按笔记首发布日期聚合观看
        by_day = {d: 0 for d in _last_n_days(range_days)}
        for n in notes_cur:
            d = iso_date(n.get("first_published_at", ""))[:10]
            if d in by_day:
                by_day[d] += _num(n.get("reads"))
        watch_trend = [{"date": d, "label": d[5:], "value": by_day[d]}
                       for d in _last_n_days(range_days)]
        watch_s = sum(v for _, v in by_day.items())
        prev_notes = [n for n in notes if _note_window(n, range_days * 2)
                      and not _note_window(n, range_days)]
        prev_watch_s = sum(_num(n.get("reads")) for n in prev_notes)
    watch_tab = {
        "kpis": [
            {"key": "曝光数", "value": exposure, "delta": None},
            {"key": "观看数", "value": reads or watch_s, "delta": _delta(watch_s, prev_watch_s)},
            {"key": "封面点击率", "value": ctr, "unit": "%", "delta": None},
            {"key": "平均观看时长", "value": _num(watch_acct.get("平均观看时长"), navg("avg_watch_seconds")),
             "unit": "秒", "delta": None},
        ],
        "trend": watch_trend,
        "funnel": {"exposure": exposure, "reads": reads or watch_s,
                   "ctr": ctr},
        "source": (watch.get("breakdown") or {}).get("观看来源", [])
                  or (watch.get("breakdown") or {}).get("来源", []),
        "timeofday": (watch.get("breakdown") or {}).get("观看时段", [])
                     or (watch.get("breakdown") or {}).get("时段", []),
        "account": {
            "观看总时长": watch_acct.get("观看总时长"),
            "视频完播率": _pct_num(watch_acct.get("视频完播率")),
            "封面点击率": _pct_num(watch_acct.get("封面点击率")),
        },
    }

    # ---------- 互动 ----------
    interact = loaded["interact"]
    ia = interact.get("account") or {}
    likes = _num(ia.get("点赞数"), nsum("likes"))
    comments = _num(ia.get("评论数"), nsum("comments"))
    collects = _num(ia.get("收藏数"), nsum("collects"))
    shares = _num(ia.get("分享数"), nsum("shares"))
    eng = _engagement(reads or watch_s, likes, collects, comments)
    interact_tab = {
        "kpis": [
            {"key": "点赞", "value": likes, "delta": None},
            {"key": "评论", "value": comments, "delta": None},
            {"key": "收藏", "value": collects, "delta": None},
            {"key": "分享", "value": shares, "delta": None},
            {"key": "互动率", "value": round(eng * 100, 2), "unit": "%", "delta": None},
        ],
        "trend": _trend_from_notes(notes_cur, range_days),
        "engagement": eng,
    }

    # ---------- 涨粉 ----------
    follower = loaded["follower"]
    fa = follower.get("account") or {}
    gained = nsum("followers_gained")
    new_follow = fa.get("新增关注")
    unfollow = fa.get("取消关注")
    visitors = _num(fa.get("主页访客"), _num(account.get("profile_visits")))
    follower_rate = round(gained / reads, 6) if reads else None
    follower_tab = {
        "kpis": [
            {"key": "净涨粉", "value": gained, "delta": None},
            {"key": "新增关注", "value": new_follow, "delta": None},
            {"key": "取消关注", "value": unfollow, "delta": None},
            {"key": "主页访客", "value": visitors, "delta": None},
            {"key": "涨粉率", "value": round(follower_rate * 100, 3) if follower_rate is not None else None,
             "unit": "%", "delta": None},
        ],
        "trend": _trend_from_notes(notes_cur, range_days, key="followers_gained"),
        "followers_gained": gained,
        "follower_rate": follower_rate,
        "account": {
            "followers": account.get("followers"),
            "following": account.get("following"),
            "likes_collects": account.get("likes_collects"),
            "period": account.get("period"),
            "净涨粉(全量)": fa.get("净涨粉"),
            "新增关注(全量)": new_follow,
            "取消关注(全量)": unfollow,
        },
    }

    return {
        "publish": publish,
        "watch": watch_tab,
        "interact": interact_tab,
        "follower": follower_tab,
    }, notes_cur, {
        "dashboard_files": {k: os.path.exists(os.path.join(dash_dir, f"{k}.json")) for k in KINDS},
        "notes_count": len(notes),
        "notes_in_range": len(notes_cur),
        "account_snapshot": account,
    }


def _first_series(doc):
    for v in (doc.get("series") or {}).values():
        if v:
            return v
    return []


def _trend_from_notes(notes_cur, range_days, key="reads"):
    by_day = {d: 0 for d in _last_n_days(range_days)}
    for n in notes_cur:
        d = iso_date(n.get("first_published_at", ""))[:10]
        if d in by_day:
            by_day[d] += _num(n.get(key))
    return [{"date": d, "label": d[5:], "value": by_day[d]}
            for d in _last_n_days(range_days)]


def _delta(cur, prev):
    if not prev:
        return None
    return round((cur - prev) / prev * 100, 1)


def build_weak_points(tabs, notes_cur, sources):
    wp = []
    watch = tabs["watch"]
    publish = tabs["publish"]
    interact = tabs["interact"]
    follower = tabs["follower"]

    # 1) 封面点击率
    ctr = watch.get("funnel", {}).get("ctr")
    if ctr is not None and ctr < CTR_WEAK_PCT:
        wp.append({
            "id": "ctr_low",
            "title": "封面点击率偏低",
            "metric": "封面点击率",
            "current": f"{ctr}%",
            "benchmark": f"≥{CTR_WEAK_PCT:.0f}%",
            "suggestion": "优先优化封面与标题：数字/冲突/人脸参考/红白品牌色，逐篇 A/B 测试。",
            "apply_to": "小红书封面/标题",
        })

    # 2) 互动率绝对偏低
    eng = interact.get("engagement") or 0
    reads = watch.get("funnel", {}).get("reads") or 0
    if reads > 0 and eng < ENGAGEMENT_WEAK:
        wp.append({
            "id": "engagement_low",
            "title": "互动率偏低",
            "metric": "互动率",
            "current": f"{eng * 100:.2f}%",
            "benchmark": f"≥{ENGAGEMENT_WEAK * 100:.0f}%",
            "suggestion": "正文加强互动引导：观点冲突、提问收尾、收藏钩子、评论区话题。",
            "apply_to": "小红书正文",
        })

    # 3) 完播率
    completion = (watch.get("account") or {}).get("视频完播率")
    if completion is not None and completion < COMPLETION_WEAK_PCT:
        wp.append({
            "id": "completion_low",
            "title": "视频完播率偏低",
            "metric": "视频完播率",
            "current": f"{completion}%",
            "benchmark": f"≥{COMPLETION_WEAK_PCT:.0f}%",
            "suggestion": "前 3 秒直接给结论/冲突/数字，缩短无效铺垫，节奏前置。",
            "apply_to": "短视频脚本",
        })

    # 4) 涨粉率
    rate = follower.get("follower_rate")
    if rate is not None and rate < FOLLOWER_RATE_WEAK:
        wp.append({
            "id": "follower_rate_low",
            "title": "涨粉率偏低",
            "metric": "涨粉率",
            "current": f"{rate * 100:.2f}%",
            "benchmark": f"≥{FOLLOWER_RATE_WEAK * 100:.2f}%",
            "suggestion": "增加关注钩子：系列内容预告、主页人设标签、结尾引导关注+收藏。",
            "apply_to": "小红书正文/主页",
        })

    # 5) 发布空窗
    gaps = sum(1 for t in publish["trend"] if t["total"] == 0)
    if gaps >= PUBLISH_GAP_DAYS:
        wp.append({
            "id": "publish_gap",
            "title": "更新节奏有断档",
            "metric": "空窗天数",
            "current": f"{gaps} 天",
            "benchmark": f"<{PUBLISH_GAP_DAYS} 天",
            "suggestion": "固定发布日历（至少隔天一篇），用选题队列兜底防止断更。",
            "apply_to": "发布节奏/总编",
        })

    # 6) 体裁结构
    pub_total = publish["kpis"][0]["value"]
    video = publish["kpis"][1]["value"]
    if pub_total >= 3 and video / pub_total < VIDEO_SHARE_WEAK:
        wp.append({
            "id": "format_imbalance",
            "title": "视频体裁占比过低",
            "metric": "视频占比",
            "current": f"{video / pub_total * 100:.0f}%",
            "benchmark": f"≥{VIDEO_SHARE_WEAK * 100:.0f}%",
            "suggestion": "尝试把高互动图文转成口播/实操类短视频，用分镜工作流批量生产。",
            "apply_to": "短视频导演",
        })

    # 7) 互动率环比下降
    prev_eng = _engagement_prev(notes_cur, tabs)
    if prev_eng is not None and eng < prev_eng * (1 - ENGAGEMENT_DROP_RATIO):
        wp.append({
            "id": "engagement_drop",
            "title": "互动率环比下降",
            "metric": "互动率",
            "current": f"{eng * 100:.2f}%",
            "benchmark": f"≥上一周期 {prev_eng * 100:.2f}%",
            "suggestion": "复盘近期选题/标题/正文结构变化，回到验证过的爆款公式。",
            "apply_to": "选题/总编",
        })

    return wp


def _engagement_prev(notes_cur, tabs):
    """上一周期互动率（用笔记明细近似）。"""
    return None  # 预留：当前实现以绝对阈值为主，环比规则有数据后自动启用


def build_dashboard(range_days=7, jobs_dir=DEFAULT_JOBS_DIR, outputs_dir=DEFAULT_OUTPUTS_DIR,
                    data_dir=DEFAULT_DATA_DIR):
    tabs, notes_cur, sources = build_tabs(range_days, data_dir)
    weak_points = build_weak_points(tabs, notes_cur, sources)
    return {
        "range_days": range_days,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tabs": tabs,
        "weak_points": weak_points,
        "sources": sources,
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", type=int, default=7, choices=(7, 30))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = build_dashboard(range_days=args.range)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json
          else f"weak_points={len(result['weak_points'])} 条："
               f"{[w['title'] for w in result['weak_points']]}")
