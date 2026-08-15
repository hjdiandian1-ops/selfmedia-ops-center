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
PLATFORM_ORDER = ("小红书", "公众号", "短视频")

# 公众号 / 短视频基准（回填口径起步）
GZH_ENGAGEMENT_WEAK = 0.005    # 互动率 <0.5%
GZH_MIN_AVG_READS = 500        # 平均阅读 <500
GZH_PUBLISH_GAP_DAYS = 7       # 空窗 ≥7 天
VIDEO_ENGAGEMENT_WEAK = 0.02   # 互动率 <2%
VIDEO_MIN_AVG_PLAY = 1000      # 平均播放 <1000
VIDEO_PUBLISH_GAP_DAYS = 7     # 空窗 ≥7 天
HIT_RATE_WEAK = 0.10           # 爆款率 <10%

# 快评阈值
XHS_QUICK_ENG = ENGAGEMENT_WEAK * 3
GZH_QUICK_ENG = GZH_ENGAGEMENT_WEAK * 2
VIDEO_QUICK_ENG = VIDEO_ENGAGEMENT_WEAK * 2
XHS_MIN_READS = 2000
GZH_MIN_READS = 500
VIDEO_MIN_READS = 3000


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


def _backfill_records(jobs_dir, range_days):
    """近 N 天全平台回填记录（publish_log.json 的 records，按时间倒序）。"""
    today = datetime.now().date()
    start = (today - timedelta(days=range_days - 1)).isoformat()
    out = []
    if os.path.isdir(jobs_dir):
        for d in sorted(os.listdir(jobs_dir)):
            data = read_json(os.path.join(jobs_dir, d, "publish_log.json")) or {}
            for r in data.get("records", []):
                day = str(r.get("collected_at") or "")[:10]
                if r.get("platform") and day >= start:
                    out.append(r)
    out.sort(key=lambda r: str(r.get("collected_at") or ""), reverse=True)
    return out


def _publish_events(jobs_dir, range_days):
    """近 N 天发布动作（publish_log.json 的 publish 列表，人工/自动发布都算）。"""
    today = datetime.now().date()
    start = (today - timedelta(days=range_days - 1)).isoformat()
    out = []
    if os.path.isdir(jobs_dir):
        for d in sorted(os.listdir(jobs_dir)):
            data = read_json(os.path.join(jobs_dir, d, "publish_log.json")) or {}
            for p in data.get("publish", []):
                day = str(p.get("at") or p.get("published_at") or "")[:10]
                if p.get("platform") and day >= start:
                    out.append({**p, "day": day})
    return out


def _platform_summary(platform, records, publishes, range_days):
    """按平台聚合回填记录 + 发布动作，产出指标/趋势/最近 10 条。"""
    recs = [r for r in records if r.get("platform") == platform]
    pubs = [p for p in publishes if p.get("platform") == platform]
    reads = sum(_num(r.get("reads")) for r in recs)
    likes = sum(_num(r.get("likes")) for r in recs)
    collects = sum(_num(r.get("collects")) for r in recs)
    comments = sum(_num(r.get("comments")) for r in recs)
    gained = sum(_num(r.get("followers_gained")) for r in recs)
    eng = round((likes + collects + comments) / reads, 4) if reads else None
    hits = sum(1 for r in recs if r.get("hit"))
    n = len(recs)
    days = _last_n_days(range_days)
    by_day = {d: {"publish": 0, "reads": 0, "followers": 0} for d in days}
    for p in pubs:
        if p["day"] in by_day:
            by_day[p["day"]]["publish"] += 1
    daily_eng = {}
    for r in recs:
        d = str(r.get("collected_at") or "")[:10]
        if d in by_day:
            by_day[d]["reads"] += _num(r.get("reads"))
            by_day[d]["followers"] += _num(r.get("followers_gained"))
            daily_eng.setdefault(d, []).append((_num(r.get("reads")), _num(r.get("engagement"))))
    for d, vals in daily_eng.items():
        total_r = sum(v[0] for v in vals)
        if total_r:
            by_day[d]["engagement"] = round(sum(v[0] * v[1] for v in vals) / total_r, 4)
    trend = {
        "labels": [d[5:] for d in days],
        "publishes": [by_day[d]["publish"] for d in days],
        "reads": [by_day[d]["reads"] for d in days],
        "engagement": [by_day[d].get("engagement") for d in days],
        "followers": [by_day[d]["followers"] for d in days],
    }
    return {
        "platform": platform,
        "has_activity": bool(pubs or recs),
        "publish_count": len(pubs),
        "backfill_count": n,
        "total_reads": reads,
        "avg_reads": round(reads / n, 1) if n else None,
        "engagement": eng,
        "hits": hits,
        "hit_rate": round(hits / n, 4) if n else None,
        "followers_gained": gained,
        "trend": trend,
        "recent": recs[:10],
    }


def _quick_label(platform, rec):
    if rec.get("hit"):
        return "爆款：延续该公式"
    eng = _num(rec.get("engagement"))
    reads = _num(rec.get("reads"))
    if reads <= 0:
        return "待回填数据"
    if platform == "小红书":
        if eng >= XHS_QUICK_ENG:
            return "互动强：复制结构"
        if reads >= XHS_MIN_READS:
            return "流量达标：优化互动"
        return "需优化封面/标题"
    if platform == "公众号":
        if eng >= GZH_QUICK_ENG:
            return "互动强：复制结构"
        if reads >= GZH_MIN_READS:
            return "流量达标：优化互动"
        return "需优化标题/打开率"
    if eng >= VIDEO_QUICK_ENG:
        return "互动强：复制结构"
    if reads >= VIDEO_MIN_READS:
        return "流量达标：优化互动"
    return "需优化前3秒/封面"


def _metric_score(value, benchmark):
    if value is None or benchmark is None or benchmark <= 0:
        return None
    ratio = value / benchmark
    return round(min(ratio, 1.25) / 1.25 * 100, 1)


def _xhs_metrics(tabs, range_days):
    watch = tabs["watch"]
    interact = tabs["interact"]
    follower = tabs["follower"]
    publish = tabs["publish"]
    ctr = watch.get("funnel", {}).get("ctr")
    eng = interact.get("engagement")
    completion = (watch.get("account") or {}).get("视频完播率")
    rate = follower.get("follower_rate")
    pub_count = (publish.get("kpis") or [{}])[0].get("value") or 0
    metrics = [
        _metric("ctr", "封面点击率", ctr, "%", CTR_WEAK_PCT, f"≥{CTR_WEAK_PCT:.0f}%"),
        _metric("engagement", "互动率", round(eng * 100, 2) if eng is not None else None,
                "%", ENGAGEMENT_WEAK * 100, f"≥{ENGAGEMENT_WEAK * 100:.0f}%"),
        _metric("completion", "完播率", completion, "%", COMPLETION_WEAK_PCT, f"≥{COMPLETION_WEAK_PCT:.0f}%"),
        _metric("follower_rate", "涨粉率", round(rate * 100, 3) if rate is not None else None,
                "%", FOLLOWER_RATE_WEAK * 100, f"≥{FOLLOWER_RATE_WEAK * 100:.2f}%"),
        _metric("publish_freq", "发布频次", pub_count, "篇", max(1, range_days // 2),
                f"≥{max(1, range_days // 2)} 篇"),
    ]
    return metrics


def _platform_metrics(platform, s, range_days):
    if platform == "公众号":
        eng_bench, eng_txt = GZH_ENGAGEMENT_WEAK, f"≥{GZH_ENGAGEMENT_WEAK * 100:.1f}%"
        avg_bench, avg_txt = GZH_MIN_AVG_READS, f"≥{GZH_MIN_AVG_READS}"
        reads_label = "平均阅读"
    else:
        eng_bench, eng_txt = VIDEO_ENGAGEMENT_WEAK, f"≥{VIDEO_ENGAGEMENT_WEAK * 100:.0f}%"
        avg_bench, avg_txt = VIDEO_MIN_AVG_PLAY, f"≥{VIDEO_MIN_AVG_PLAY}"
        reads_label = "平均播放"
    metrics = [
        _metric("engagement", "互动率", round(s["engagement"] * 100, 2) if s["engagement"] is not None else None,
                "%", eng_bench * 100, eng_txt),
        _metric("avg_reads", reads_label, s["avg_reads"], "", avg_bench, avg_txt),
        _metric("hit_rate", "爆款率", round(s["hit_rate"] * 100, 1) if s["hit_rate"] is not None else None,
                "%", HIT_RATE_WEAK * 100, f"≥{HIT_RATE_WEAK * 100:.0f}%"),
        _metric("publish_freq", "发布频次", s["publish_count"], "篇", max(1, range_days // 7),
                f"≥{max(1, range_days // 7)} 篇"),
        _metric("follower_rate", "涨粉率", None, "%", FOLLOWER_RATE_WEAK * 100,
                f"≥{FOLLOWER_RATE_WEAK * 100:.2f}%", available=False),
    ]
    if not s.get("has_activity", True):
        for m in metrics:
            m["available"] = False
            m["score"] = None
    return metrics


def _metric(key, label, value, unit, benchmark, benchmark_text, available=None):
    avail = value is not None if available is None else available
    return {
        "key": key, "label": label, "value": value, "unit": unit,
        "benchmark": benchmark, "benchmark_text": benchmark_text,
        "available": avail,
        "score": _metric_score(value, benchmark) if avail else None,
    }


def _build_platform_weak(platform, s):
    wp = []
    if s["backfill_count"] == 0:
        wp.append({
            "id": f"{platform}_no_data", "title": "缺少回填数据",
            "metric": "回填数", "current": "0 条", "benchmark": "≥1 条",
            "suggestion": "发布后在成品库标记发布，48h 内回填阅读/赞/藏/评，看板才能诊断。",
            "apply_to": "归档发布员",
        })
        return wp
    if s["engagement"] is not None:
        bench = GZH_ENGAGEMENT_WEAK if platform == "公众号" else VIDEO_ENGAGEMENT_WEAK
        if s["engagement"] < bench:
            if platform == "公众号":
                wp.append({
                    "id": "gzh_engagement_low", "title": "互动率偏低", "metric": "互动率",
                    "current": f"{s['engagement'] * 100:.2f}%", "benchmark": f"≥{bench * 100:.1f}%",
                    "suggestion": "公众号正文加强观点密度与转发引导：金句、清单、收藏钩子，结尾抛话题。",
                    "apply_to": "公众号主编",
                })
            else:
                wp.append({
                    "id": "video_engagement_low", "title": "互动率偏低", "metric": "互动率",
                    "current": f"{s['engagement'] * 100:.2f}%", "benchmark": f"≥{bench * 100:.0f}%",
                    "suggestion": "前 3 秒强钩子 + 高信息密度，结尾引导评论/收藏/关注等深度行为。",
                    "apply_to": "短视频导演",
                })
    avg_bench = GZH_MIN_AVG_READS if platform == "公众号" else VIDEO_MIN_AVG_PLAY
    if s["avg_reads"] is not None and s["avg_reads"] < avg_bench:
        wp.append({
            "id": f"{platform}_reads_low",
            "title": "平均阅读/播放偏低", "metric": "平均阅读/播放",
            "current": f"{s['avg_reads']:.0f}", "benchmark": f"≥{avg_bench}",
            "suggestion": "优化标题与首屏信息：数字/冲突/悬念前置，对标近期平台爆款标题公式。",
            "apply_to": "资深采编",
        })
    gap_limit = GZH_PUBLISH_GAP_DAYS if platform == "公众号" else VIDEO_PUBLISH_GAP_DAYS
    gaps = sum(1 for v in s["trend"]["publishes"] if v == 0)
    if s["publish_count"] > 0 and gaps >= gap_limit:
        wp.append({
            "id": f"{platform}_publish_gap", "title": "更新节奏有断档", "metric": "空窗天数",
            "current": f"{gaps} 天", "benchmark": f"<{gap_limit} 天",
            "suggestion": "固定发布日历（至少每周 1-2 篇），用选题队列兜底防止断更。",
            "apply_to": "发布节奏/总编",
        })
    if s["backfill_count"] >= 5 and s["hit_rate"] is not None and s["hit_rate"] < HIT_RATE_WEAK:
        wp.append({
            "id": f"{platform}_no_hit", "title": "爆款率偏低", "metric": "爆款率",
            "current": f"{s['hit_rate'] * 100:.0f}%", "benchmark": f"≥{HIT_RATE_WEAK * 100:.0f}%",
            "suggestion": "回到爆款跟踪的高频公式池选题，参考平台算法规则做标题/封面强化。",
            "apply_to": "选题/总编",
        })
    return wp


def _score_and_radar(metrics):
    scores = [m["score"] for m in metrics if m.get("available") and m.get("score") is not None]
    score = round(sum(scores) / len(scores), 1) if scores else None
    radar = {
        "axes": [{
            "label": m["label"], "value": m.get("score"),
            "available": m.get("available", False),
            "benchmark_text": m.get("benchmark_text", ""),
        } for m in metrics],
    }
    return score, radar


def _focus(platform, metrics, weak):
    cands = [m for m in metrics if m.get("available") and m.get("score") is not None]
    if cands:
        m = min(cands, key=lambda x: x["score"])
        if m["score"] >= 100:
            return "整体健康：保持当前选题、发布节奏与公式库迭代。"
        hit = next((w for w in weak if w.get("metric") == m["label"]), None)
        if hit:
            return f"{m['label']}偏低：{hit['suggestion']}"
        return f"{m['label']}偏低：对照基准 {m['benchmark_text']} 优化。"
    if weak:
        return weak[0]["suggestion"]
    return "先回填/导入数据后开始诊断。"


def _overview(platforms, range_days):
    scores = [v["health_score"] for v in platforms.values() if v["health_score"] is not None]
    health = round(sum(scores) / len(scores), 1) if scores else None
    worst = None
    for p, info in platforms.items():
        if info["health_score"] is not None and (worst is None
                                                 or info["health_score"] < worst[1]["health_score"]):
            worst = (p, info)
    focus = worst[1]["focus"] if worst else "先回填/导入数据后开始诊断。"
    radar = {
        "axes": [{
            "label": p, "value": info["health_score"],
            "available": info["health_score"] is not None,
            "benchmark_text": "满分 100",
        } for p, info in platforms.items()],
    }
    return {"health_score": health, "focus": focus, "radar": radar}


def _save_diagnostics(data_dir, payload):
    path = os.path.join(data_dir, "dashboard", "diagnostics.json")
    prev = read_json(path) or {}
    prev_platforms = prev.get("platforms") or {}
    deltas = {}
    for p, info in (payload.get("platforms") or {}).items():
        cur = info.get("health_score")
        old = (prev_platforms.get(p) or {}).get("health_score")
        if cur is not None and old is not None:
            deltas[p] = round(cur - old, 1)
    prev_ids = set(prev.get("weak_points") or [])
    new_ids = [w["id"] for p in (payload.get("platforms") or {}).values()
               for w in p.get("weak_points", []) if w["id"] not in prev_ids]
    snapshot = {
        "generated_at": payload["generated_at"],
        "previous_at": prev.get("generated_at"),
        "platforms": {p: {"health_score": info.get("health_score")}
                      for p, info in (payload.get("platforms") or {}).items()},
        "weak_points": [w["id"] for p in (payload.get("platforms") or {}).values()
                        for w in p.get("weak_points", [])],
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return {
        "generated_at": snapshot["generated_at"],
        "previous_at": snapshot["previous_at"],
        "deltas": deltas,
        "new_weak_points": new_ids,
    }


def build_dashboard(range_days=7, jobs_dir=DEFAULT_JOBS_DIR, outputs_dir=DEFAULT_OUTPUTS_DIR,
                    data_dir=DEFAULT_DATA_DIR):
    tabs, notes_cur, sources = build_tabs(range_days, data_dir)
    weak_points = build_weak_points(tabs, notes_cur, sources)
    records = _backfill_records(jobs_dir, range_days)
    publishes = _publish_events(jobs_dir, range_days)
    platforms = {}
    for p in PLATFORM_ORDER:
        s = _platform_summary(p, records, publishes, range_days)
        if p == "小红书":
            metrics = _xhs_metrics(tabs, range_days)
            weak = weak_points
        else:
            metrics = _platform_metrics(p, s, range_days)
            weak = _build_platform_weak(p, s)
        score, radar = _score_and_radar(metrics)
        recs = [{**r, "quick": _quick_label(p, r)} for r in s["recent"]]
        platforms[p] = {
            "health_score": score,
            "focus": _focus(p, metrics, weak),
            "radar": radar,
            "metrics": metrics,
            "weak_points": weak,
            "trend": s["trend"],
            "recent": recs,
            "totals": {
                "publish_count": s["publish_count"],
                "backfill_count": s["backfill_count"],
                "total_reads": s["total_reads"],
                "avg_reads": s["avg_reads"],
                "engagement": s["engagement"],
                "hits": s["hits"],
                "hit_rate": s["hit_rate"],
            },
        }
    overview = _overview(platforms, range_days)
    overview["recent"] = sorted(
        (r for p in platforms.values() for r in p["recent"]),
        key=lambda r: str(r.get("collected_at") or ""), reverse=True)[:10]
    result = {
        "range_days": range_days,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tabs": tabs,
        "weak_points": weak_points,
        "sources": sources,
        "overview": overview,
        "platforms": platforms,
    }
    result["diagnostics"] = _save_diagnostics(data_dir, result)
    return result


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
