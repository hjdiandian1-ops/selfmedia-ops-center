#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选题推荐器 (Hot Topics → Topic Suggestions)
============================================
读取最近的热点雷达，按「日选题 / 周选题」双池推荐：
  - 日选题：重时效/热度（门槛：时效≥4 即 24h 内，且热度≥6），按
    时效×1.2 + 热度×1.2 + 质量×0.4 排序，默认 8 条。
  - 周选题：重内容质量/平台信号，按 质量×1.2 + 热度×0.5 + 时效×0.3 排序，
    默认 10 条。
质量分 = 表达 + 搜索 + 持久 + 独特（各 0-5）+ 跨源（每多一源 +4）。
IP 垂直度为准入门槛（ip < 1 不推荐），不进入总分；合规命中一票否决。

时效连续分 = max(0, 6 − hours/12)；热度分 = min(10, (11−rank) + 同源热度微调 0~1)。
文本维度用「标题 + 雷达摘要」匹配（无摘要源仅标题），不做统一保底分。

用法：
    python3 scripts/suggest_topics.py                          # 最新雷达，落盘双池选题推荐
    python3 scripts/suggest_topics.py --date 2026-08-06        # 指定日期
    python3 scripts/suggest_topics.py --json                   # 只打印 JSON，不落盘
    python3 scripts/suggest_topics.py --daily-top 8 --weekly-top 10

退出码：0 = 有候选；1 = 无热点雷达文件或无可推荐条目。仅依赖标准库。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

MATERIALS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "materials"))
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LEXICON_FILE = os.path.join(ROOT, "data", "topics", "lexicon.json")
PREF_FILE = os.path.join(ROOT, "data", "topics", "preferences.json")
NICHES_FILE = os.path.join(ROOT, "data", "topics", "niches.json")

# 公开仓库兜底词库（完整精选词库在私有 data/topics/lexicon.json，不进公开仓库）
GENERIC_LEXICON = {
    "ip": {"AI": 1, "工具": 1, "创业": 1, "效率": 1},
    "emotion": ["暴涨", "暴跌", "震惊", "突破", "新高"],
    "search": ["教程", "怎么", "如何", "对比", "价格"],
    "durable": ["清单", "步骤", "案例", "指南", "报告"],
    "unique": ["风险", "争议", "警告", "真相", "没想到"],
    "identity": ["普通人", "年轻人", "创业者", "打工人", "学生"],
}


def _load_lexicon():
    """优先加载私有精选词库；缺失时用通用兜底词库（保证公开仓库可运行）。"""
    try:
        with open(LEXICON_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and all(k in data for k in ("ip", "emotion", "search", "durable", "unique", "identity")):
            return data
    except Exception:
        return GENERIC_LEXICON
    return GENERIC_LEXICON


_LEXICON = _load_lexicon()


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def load_prefs():
    return _read_json(PREF_FILE, {}) or {}


def load_niches():
    return _read_json(NICHES_FILE, {}) or {}


def match_niches(title, summary, prefs, niches):
    """按用户偏好的「平台·赛道」关键词匹配标题+摘要，返回命中的赛道名。"""
    text = (str(title or "") + " " + str(summary or "")).lower()
    hits = []
    for platform, names in (prefs.get("platforms") or {}).items():
        for name in names:
            for kw in (niches.get(platform) or {}).get(name, []):
                if str(kw).lower() in text:
                    hits.append(f"{platform}·{name}")
                    break
    return hits

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from fetch_hot_topics import COMPLIANCE_BLOCK, OVERSEAS_SOURCES
except ImportError:
    COMPLIANCE_BLOCK = []
    OVERSEAS_SOURCES = ()

# ---------- 评分常量（阈值集中管理，便于按数据反馈调参） ----------
FRESH_MAX = 6.0            # 时效满分（0 小时）
FRESH_DECAY_HOURS = 12.0   # 时效分 = max(0, 6 − hours/12)
STALE_HOURS = 72.0         # >72h 视为过时，不进任何池
HEAT_MAX = 10.0            # 热度满分
CROSS_SOURCE_BONUS = 4     # 每多一个独立信息源印证，+4 分
IP_GATE = 1.0              # IP 垂直度准入门槛：低于此值不推荐（不入总分）
MAX_DIM = 5.0              # 各文本维度原始分上限

DAILY_TOP = 8
WEEKLY_TOP = 10
DAILY_FRESH_GATE = 4.0     # ≤24h（6 − 24/12 = 4）
DAILY_HEAT_GATE = 6.0
WEEKLY_HEAT_GATE = 5.0
DAILY_FRESH_W, DAILY_HEAT_W, DAILY_QUALITY_W = 1.2, 1.2, 0.4
WEEKLY_QUALITY_W, WEEKLY_HEAT_W, WEEKLY_FRESH_W = 1.2, 0.5, 0.3

# IP 相关关键词权重（完整版来自私有 data/topics/lexicon.json）
IP_KEYWORDS = _LEXICON["ip"]

# 标题冲击力：具体数字/问号/悬念/情绪词
IMPACT_RE = re.compile(
    r"\d+(?:\.\d+)?[亿万元%％倍]|[？?!！]|竟然|居然|秘密|真相|别|不再|反|离谱|爆|疯|狂|涨|跌|赚|亏|洗牌|创纪录"
    r"|炸裂|碾压|里程碑|新高|纪录|首个|最快|最强|断层|血洗"
)
# 对比冲突：从…到 / vs / 却 / 但 / 还是
CONTRAST_RE = re.compile(r"从.*到|vs|对比|还是|却|但|而|反")
# 情绪/搜索/持久/独特/身份词（完整版来自私有 data/topics/lexicon.json）
EMOTION_WORDS = _LEXICON["emotion"]
SEARCH_KEYWORDS = _LEXICON["search"]
DURABLE_KEYWORDS = _LEXICON["durable"]
UNIQUE_WORDS = _LEXICON["unique"]
IDENTITY_WORDS = _LEXICON["identity"]

# 钱/成本 → 硬核拆解；公司/创业/创始人 → 商业对话；其余 → 商业观察
DECONSTRUCT_RE = re.compile(r"钱|赚|成本|价|利润|收益|收入|融资|规模|订单")
DIALOGUE_RE = re.compile(r"公司|创业|创始人|融资|企业|老板|团队")

VIEW_ORDER = {"【硬核拆解】": 0, "【商业对话】": 1, "【商业观察】": 2}
FORMULA_TAGS = {
    "数字冲击": r"\d",
    "身份代入": r"我|你|我们|打工人|学生|程序员|创业者",
    "冲突对比": CONTRAST_RE,
    "悬念好奇": r"[？?]|为什么|真相|秘密",
    "反常识": r"竟然|居然|离谱|反|别",
}

# 雷达行尾热度：`（9）`（推楼）/ `（500+）`（谷歌趋势）/ `（100.2万热度）`（今日热榜）
HEAT_SUFFIX_RE = re.compile(r"\s*（\s*([\d.]+)(万)?(\+)?(?:热度|浏览|阅读)?\s*）\s*$")


def normalize_title(t):
    """去链接/序号/括号注解，压缩空白。"""
    t = re.sub(r"（\[链接\]\(.*?\)）", "", t)
    t = re.sub(r"^\d+[\.、．]\s*", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def extract_heat(title):
    """提取行尾 `（数字[万][+][热度]）` 为热度值；返回 (干净标题, 原始标注, 数值|None)。

    仅允许裸数字 ≤2 位（如推楼 `（9）`），4 位年份不会误判；带 `万/+`/单位任意数字均可。
    """
    m = HEAT_SUFFIX_RE.search(title)
    if not m:
        return title.strip(), "", None
    digits = m.group(1).replace(".", "")
    if not (m.group(2) or m.group(3)) and len(digits) > 2:
        return title.strip(), "", None
    value = float(m.group(1))
    if m.group(2) == "万":
        value *= 10000
    return title[: m.start()].strip(), m.group(0).strip(), value


def parse_radar(path):
    """解析热点雷达 md → [(title, source, link, rank, published_at, heat, summary)]"""
    rows = []
    source = ""
    for ln in open(path, encoding="utf-8"):
        ln = ln.rstrip("\n")
        if ln.startswith("## "):
            source = ln[3:].strip()
            continue
        m = re.match(
            r"\s*(\d+)[\.、．]\s*(.+?)(?:（\[链接\]\((.*?)\)）)?"
            r"(?:（发布于 ([^）]+)）)?(?:（摘要 ([^）]*)）)?(?:\s*｜.*)?$", ln)
        if m and source:
            title, heat_raw, heat = extract_heat(m.group(2).strip())
            rows.append((title, source, m.group(3) or "",
                         int(m.group(1)), (m.group(4) or "").strip(), heat,
                         (m.group(5) or "").strip()))
    return rows


def _parse_dt(raw):
    """把 RSS RFC822 / 推楼 YYYYMMDDHH / ISO 时间解析为带时区 datetime。"""
    text = str(raw).strip()
    try:
        return parsedate_to_datetime(text)  # RSS RFC822: Sat, 08 Aug 2026 ...
    except (TypeError, ValueError):
        pass
    # 推楼 1 号 hour_key：`2026081223` 按北京时间（UTC+8）解释
    for fmt in ("%Y%m%d%H", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).replace(
                tzinfo=timezone(timedelta(hours=8)))
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt
    except ValueError:
        return None


def fresh_info(published_at):
    """按发布时间给连续时效分：max(0, 6 − hours/12)；>72h 过时（0 分），未知 0 分。"""
    if not published_at:
        return {"label": "时效未知", "hours": None, "score": 0.0, "stale": False}
    dt = _parse_dt(published_at)
    if dt is None:
        return {"label": "时效未知", "hours": None, "score": 0.0, "stale": False}
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    hours = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)
    if hours > STALE_HOURS:
        return {"label": f"{int(hours // 24)} 天前", "hours": round(hours, 1),
                "score": 0.0, "stale": True}
    score = round(max(0.0, FRESH_MAX - hours / FRESH_DECAY_HOURS), 1)
    label = ("12 小时内" if hours <= 12 else "24 小时内" if hours <= 24
             else "2 天内" if hours <= 48 else "3 天内")
    return {"label": label, "hours": round(hours, 1), "score": score, "stale": False}


def _hits(words, title):
    return sum(1 for w in words if w in title)


def score_dimensions(text):
    """文本侧五维：IP 垂直度 / 表达势能 / 搜索价值 / 持久价值 / 观点独特性（各 0-5）。

    入参为「标题 + 摘要」拼接文本；无特征就 0 分，不做统一保底。
    """
    ip = min(MAX_DIM, sum(IP_KEYWORDS.get(w, 0) for w in IP_KEYWORDS if w in text))
    impact = 0
    if IMPACT_RE.search(text):
        impact += 2
    if CONTRAST_RE.search(text):
        impact += 1
    impact = min(MAX_DIM, impact + _hits(EMOTION_WORDS, text))
    search = min(MAX_DIM, _hits(SEARCH_KEYWORDS, text))
    durable = min(MAX_DIM, _hits(DURABLE_KEYWORDS, text))
    unique = min(MAX_DIM, _hits(UNIQUE_WORDS, text) + _hits(IDENTITY_WORDS, text))
    return {"ip": ip, "impact": impact, "search": search,
            "durable": durable, "unique": unique}


def score_item(title):
    """兼容旧接口：展示侧文本分（表达+搜索+持久+独特，不含 IP/时效/热度/跨源）。"""
    d = score_dimensions(title)
    return round(d["impact"] + d["search"] + d["durable"] + d["unique"], 1)


def suggest_view(title):
    if DECONSTRUCT_RE.search(title):
        return "【硬核拆解】"
    if DIALOGUE_RE.search(title):
        return "【商业对话】"
    return "【商业观察】"


def suggest_formulas(title):
    tags = [name for name, pat in FORMULA_TAGS.items() if re.search(pat, title)]
    return tags or ["反常识"]


# 弱信号新闻/资讯类标题可用的通用爆款公式池（无强特征时轮换，避免整版同款）
WEAK_FORMULA_POOL = [
    ("#5 为什么 [话题] 会改变一切", "反常识"),
    ("#23 给 [一群人] 的一个忠告", "身份代入"),
    ("#12 看完这个，你的 [想法] 会不再相同", "悬念好奇"),
    ("#7 [一群人] 不会告诉你的建议", "好奇缺口"),
]


def _pick_formula_type(title):
    """按标题特征选主公式类型（强信号优先；无信号返回 None）。"""
    if re.search(r"如何|怎么|教程|步骤|技巧|方法|窍门|清单|指南|避坑|模板|攻略", title):
        return "数字冲击"
    if re.search(r"为什么|看完这个|真相|秘密|背后|内幕|泄露|竟然|居然", title):
        return "悬念好奇"
    if re.search(r"vs|对比|还是|却|但|从.*到", title):
        return "冲突对比"
    if re.search(r"离谱|颠覆|反常识|别|不再|警惕", title):
        return "反常识"
    if re.search(r"打工人|程序员|创业者|宝妈|自由职业|独立开发者|创作者|学生|老板|普通人|年轻人|中年人|我|你|我们", title):
        return "身份代入"
    return None


def suggest_formula_detail(title, tags=None):
    """按标题特征给出具体编号+模板（对照 dbs-xhs-title 公式库），弱信号附备选公式。"""
    primary = _pick_formula_type(title)
    if primary == "身份代入":
        if re.search(r"打工人|程序员|创业者|宝妈|自由职业|独立开发者|创作者|学生|老板|普通人|年轻人|中年人", title):
            return "#23 给 [一群人] 的一个忠告（身份代入）"
        if "每个人" in title:
            return "#21 给每个 [年龄层/身份] 人的终极 [建议]（身份代入）"
        if re.search(r"的人", title):
            return "#24 [指出特征] 的人（身份代入）"
        return "#23 给 [一群人] 的一个忠告（身份代入）"
    if primary == "数字冲击":
        if re.search(r"步骤|方法", title):
            return "#27 搞懂 [话题] 的 [数字] 个步骤（数字冲击）"
        return "#26 [数字] 个达成 [结果] 的小窍门（数字冲击）"
    if primary == "冲突对比":
        return "#52 [好的特质] VS [坏的特质] - 如何区分（冲突对比）"
    if primary == "悬念好奇":
        return "#12 看完这个，你的 [想法] 会不再相同（悬念好奇）"
    if primary == "反常识":
        return "#1 为什么 [每个人都觉得好的事] 其实对你有害？（反常识）"
    # 弱信号：按标题稳定轮换一个主推，并列出全部备选，供采编/主编挑选
    idx = sum(ord(ch) for ch in title) % len(WEAK_FORMULA_POOL)
    main, main_tag = WEAK_FORMULA_POOL[idx]
    alts = [f"{tpl}（{tag}）" for j, (tpl, tag) in enumerate(WEAK_FORMULA_POOL) if j != idx]
    return f"{main}（{main_tag}）；备选：" + " / ".join(alts)


def score_rows(rows):
    """雷达行 → 已评分条目（连续时效、rank+热度微调、标题+摘要文本五维）。"""
    scored = []
    for t, s, l, r, pub, heat, summary in rows:
        fresh = fresh_info(pub)
        formulas = suggest_formulas(t)
        full_text = t + (" " + summary if summary else "")
        scored.append({
            "title": normalize_title(t), "source": s, "link": l, "rank": r,
            "heat": heat, "heat_raw": heat if heat is not None else "",
            "summary": summary, "fresh": fresh, "published_at": pub,
            "dims": score_dimensions(full_text),
            "view": suggest_view(t), "formulas": formulas,
            "formula_detail": suggest_formula_detail(t, formulas),
            "compliance": "海外源·需人工复核（国内可发布性）"
                          if any(ov in s for ov in OVERSEAS_SOURCES) else "",
        })
    # 热度：同源内原始热度归一化 0~1 作为微调；主分来自榜单 rank（11-rank）
    for src in {it["source"] for it in scored}:
        vals = [it["heat"] for it in scored if it["source"] == src and it["heat"] is not None]
        mx = max(vals) if vals else None
        for it in scored:
            if it["source"] != src:
                continue
            heat_norm01 = (it["heat"] / mx) if (mx and it["heat"] is not None) else 0.0
            it["heat_norm01"] = round(min(1.0, heat_norm01), 2)
            it["heat_score"] = round(min(HEAT_MAX, (11 - it["rank"]) + it["heat_norm01"]), 1)
    for it in scored:
        finalize_score(it)
    return scored


def finalize_score(it, cross_bonus=0, source_count=1):
    """写原始分拆解与双池排序分（IP 为准入门槛，不进入任何总分）。"""
    d = it["dims"]
    bd = {
        "freshness": round(it["fresh"]["score"], 1),
        "heat": round(it["heat_score"], 1),
        "impact": round(d["impact"], 1),
        "search": round(d["search"], 1),
        "durable": round(d["durable"], 1),
        "unique": round(d["unique"], 1),
        "cross_source": round(cross_bonus, 1),
    }
    it["score_breakdown"] = bd
    it["source_count"] = source_count
    it["score"] = round(sum(bd.values()), 1)  # 展示用原始合计
    it["quality"] = round(d["impact"] + d["search"] + d["durable"] + d["unique"] + cross_bonus, 1)
    it["daily_score"] = round(
        it["fresh"]["score"] * DAILY_FRESH_W + it["heat_score"] * DAILY_HEAT_W
        + it["quality"] * DAILY_QUALITY_W, 1)
    it["weekly_score"] = round(
        it["quality"] * WEEKLY_QUALITY_W + it["heat_score"] * WEEKLY_HEAT_W
        + it["fresh"]["score"] * WEEKLY_FRESH_W, 1)
    return it


def _dedupe_key(title):
    """跨源去重 key：去掉资讯后缀、冒号补充说明与常见发布动词，取核心实体词。"""
    t = re.sub(r"（[^）]*资讯）", "", title)
    t = re.sub(r"[：:].*$", "", t)
    t = re.sub(r"发布|上线|宣布|正式|推出|亮相|更新|新增|公布|来袭", "", t)
    t = re.sub(r"[\s：:，。、\-—（）()]+", "", t).lower()
    return t[:16]


def dedupe_and_rank(scored):
    """跨源去重：同主题多源计一次，每多一个源 +CROSS_SOURCE_BONUS。"""
    seen, deduped = {}, []
    for it in scored:
        key = _dedupe_key(it["title"])
        if key in seen:
            base = seen[key]
            base["source"] += " + " + it["source"]
            base["source_count"] += 1
            base["heat_raw"] = base["heat_raw"] or it["heat_raw"]
            base["heat_score"] = max(base["heat_score"], it["heat_score"])
            base["compliance"] = base["compliance"] or it["compliance"]
            for k in ("impact", "search", "durable", "unique", "ip"):
                base["dims"][k] = max(base["dims"][k], it["dims"][k])
            if it["fresh"]["hours"] is not None and (
                    base["fresh"]["hours"] is None or it["fresh"]["hours"] < base["fresh"]["hours"]):
                base["fresh"] = it["fresh"]
            finalize_score(base, cross_bonus=CROSS_SOURCE_BONUS * (base["source_count"] - 1),
                           source_count=base["source_count"])
            continue
        it["source_count"] = 1
        seen[key] = it
        deduped.append(it)
    deduped.sort(key=lambda x: (-x["score"], -x["dims"]["ip"], x["rank"]))
    return deduped


def build_pools(deduped, daily_top=DAILY_TOP, weekly_top=WEEKLY_TOP):
    """双池：日选题重时效热度（门槛），周选题重内容质量；同一主题可同时进两池。"""
    daily = [it for it in deduped
             if it["fresh"]["hours"] is not None
             and it["fresh"]["score"] >= DAILY_FRESH_GATE
             and it["heat_score"] >= DAILY_HEAT_GATE]
    daily.sort(key=lambda x: (-x["daily_score"], -x["dims"]["ip"], x["rank"]))
    weekly = [it for it in deduped
              if it["fresh"]["hours"] is not None and not it["fresh"].get("stale")
              and (it["dims"]["search"] > 0 or it["dims"]["durable"] > 0
                   or it["dims"]["unique"] > 0 or it["heat_score"] >= WEEKLY_HEAT_GATE)]
    weekly.sort(key=lambda x: (-x["weekly_score"], -x["dims"]["ip"], x["rank"]))
    return daily[:daily_top], weekly[:weekly_top]


def _candidate_lines(pool_name, picks, score_key, score_label, formula_note):
    lines = [f"## {pool_name}（{len(picks)} 条 · {formula_note}）", ""]
    for i, it in enumerate(picks, 1):
        b = it["score_breakdown"]
        breakdown = (f"时效 {b['freshness']}｜热度 {b['heat']}｜表达 {b['impact']}"
                     f"｜搜索 {b['search']}｜持久 {b['durable']}｜独特 {b['unique']}"
                     f"｜跨源 +{b['cross_source']}｜合计 {it['score']}")
        heat_desc = f"（原始热度 {it['heat_raw']}）" if it.get("heat_raw") else ""
        lines += [
            f"### 候选 {i} ⭐{score_label} {it[score_key]:.1f}",
            f"- 主题方向：{it['title']}",
            f"- 命中热点：{it['source']}（rank {it['rank']}，{it['source_count']} 源印证）",
            f"- 命中赛道：{'、'.join(it.get('niches') or []) or '默认推荐（未设置偏好）'}",
            f"- 热度：{it['heat_score']:.1f}/10{heat_desc}",
            f"- 评分构成：{breakdown}",
            f"- 池内排序：日 {it['daily_score']} ｜ 周 {it['weekly_score']}",
            f"- 建议视角：{it['view']}",
            f"- 建议标题公式：{it['formula_detail']}（对照 dbs-xhs-title 公式库）",
            f"- 合规：{it['compliance'] or '国内源·正常'}",
            f"- 时效：{it['fresh']['label']}"
            + (f"（{it['fresh']['hours']}h）" if it["fresh"]["hours"] is not None else ""),
            "- 📕 封面套路观察：（采编补充：参考同类爆款封面的构图/钩子/配色）",
            f"- 原文链接：{it['link'] or '无'}",
            "",
        ]
    return lines


def main():
    ap = argparse.ArgumentParser(description="选题推荐器（日/周双池）")
    ap.add_argument("--date", default="", help="热点雷达日期 YYYY-MM-DD（默认最新）")
    ap.add_argument("--daily-top", type=int, default=DAILY_TOP, help=f"日选题数（默认 {DAILY_TOP}）")
    ap.add_argument("--weekly-top", type=int, default=WEEKLY_TOP, help=f"周选题数（默认 {WEEKLY_TOP}）")
    ap.add_argument("--top", type=int, default=None, help="兼容旧参数：等价于 --daily-top")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.top is not None:
        args.daily_top = args.top

    if args.date:
        candidates = [os.path.join(MATERIALS_DIR, args.date[:7], f"{args.date}_热点雷达.md")]
    else:
        radar_paths = sorted(
            os.path.join(root, f)
            for root, _, files in os.walk(MATERIALS_DIR)
            for f in files if f.endswith("_热点雷达.md")
        )
        candidates = radar_paths[-1:] if radar_paths else []
    if not candidates or not os.path.exists(candidates[0]):
        print("❌ 未找到热点雷达文件。请先运行 python3 scripts/fetch_hot_topics.py 采集。", file=sys.stderr)
        sys.exit(1)
    radar_path = candidates[0]

    rows = parse_radar(radar_path)
    if not rows:
        print(f"❌ 热点雷达 {radar_path} 无有效条目。", file=sys.stderr)
        sys.exit(1)

    # 合规初筛：命中关键词的条目不进候选（与采集器同规则，一票否决）
    before = len(rows)
    rows = [r for r in rows if not any(kw in r[0] for kw in COMPLIANCE_BLOCK)]
    if len(rows) < before:
        print(f"⚠️ 合规初筛剔除 {before - len(rows)} 条", file=sys.stderr)

    scored = [it for it in score_rows(rows) if it["dims"]["ip"] >= IP_GATE]
    if len(scored) < len(rows):
        print(f"⚠️ IP 垂直度门槛（≥{IP_GATE}）剔除 {len(rows) - len(scored)} 条", file=sys.stderr)
    prefs = load_prefs()
    niches = load_niches()
    selected = prefs.get("platforms") or {}
    if selected:
        for it in scored:
            it["niches"] = match_niches(it["title"], it.get("summary"), prefs, niches)
        filtered = [it for it in scored if it["niches"]]
        total_sel = sum(len(v) for v in selected.values())
        print(f"🎯 偏好赛道过滤：{total_sel} 个赛道 → 保留 {len(filtered)}/{len(scored)} 条")
        if filtered:
            scored = filtered
        else:
            print("⚠️ 偏好过滤后无候选，回退默认推荐", file=sys.stderr)
    deduped = dedupe_and_rank(scored)
    daily, weekly = build_pools(deduped, args.daily_top, args.weekly_top)
    if not daily and not weekly:
        print("❌ 合规/IP 门槛后无候选，请先检查热点雷达数据。", file=sys.stderr)
        sys.exit(1)
    today = datetime.now().strftime("%Y-%m-%d")
    month = today[:7]

    if args.json:
        print(json.dumps({"daily": daily, "weekly": weekly}, ensure_ascii=False, indent=2))
        return

    out_dir = os.path.join(MATERIALS_DIR, month)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{today}_选题推荐.md")

    lines = [
        f"# 🎯 选题推荐（{today}）",
        "",
        f"> 依据：{os.path.basename(radar_path)}｜双池：日选题重时效热度（门槛 24h 内且热度≥6），周选题重内容质量",
        "> 时效连续分 = max(0, 6 − 小时/12)；热度 = (11−rank) + 同源热度微调 0~1；质量 = 表达+搜索+持久+独特+跨源",
        "> IP 垂直度为准入门槛（ip < 1 不推荐），不进入总分；合规命中一票否决；无特征文本维度为 0 分（不加保底）。",
        "> 算法参考：research/平台推荐算法与选题评分.md（抖音多目标推荐+搜索联动 / 小红书点击率与收藏权重 / 公众号社交分发+搜一搜）",
        "> 用法：候选必须由用户（老板）拍板后进入 `topic` 态，禁止自动选第 1 条；海外源候选需人工复核国内可合规发布。",
        "> 📕 封面套路观察由采编在创作前按 `guizang-social-card-skill`/小红书对标补充。",
        "",
    ]
    lines += _candidate_lines("日选题", daily, "daily_score", "日分",
                              "时效×1.2 + 热度×1.2 + 质量×0.4 排序")
    lines += _candidate_lines("周选题", weekly, "weekly_score", "周分",
                              "质量×1.2 + 热度×0.5 + 时效×0.3 排序")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"📁 选题推荐已落盘：{out_path}（日 {len(daily)} 条 ｜ 周 {len(weekly)} 条）")
    for label, picks, key in (("日", daily, "daily_score"), ("周", weekly, "weekly_score")):
        for it in picks:
            flag = "⚠️海外" if it["compliance"] else ""
            fresh = f"｜时效 {it['fresh']['label']}"
            if it["fresh"]["hours"] is not None:
                fresh += f" {it['fresh']['hours']}h"
            print(f"   [{label}] ⭐{it[key]:.1f} {it['title']} ← {it['source']} {flag}{fresh}")


if __name__ == "__main__":
    main()
