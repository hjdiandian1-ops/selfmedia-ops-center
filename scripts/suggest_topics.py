#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选题推荐器 (Hot Topics → Topic Suggestions)
============================================
读取最近的热点雷达，按「小吴聊」IP 相关度 + 标题冲击力 + 跨源热度排序，
输出 3-5 个选题候选（含建议切入视角、标题公式类型、封面套路观察位），
供总编/资深采编决策选题，打通「RSSHub → 热点雷达 → 选题」数据流。

用法：
    python3 scripts/suggest_topics.py                     # 用最新热点雷达，落盘 选题推荐.md
    python3 scripts/suggest_topics.py --date 2026-08-06   # 指定日期
    python3 scripts/suggest_topics.py --json              # 只打印 JSON，不落盘
    python3 scripts/suggest_topics.py --top 5             # 候选数（默认 5）

退出码：0 = 有候选；1 = 无热点雷达文件或无可推荐条目。仅依赖标准库。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

MATERIALS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "materials"))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from fetch_hot_topics import COMPLIANCE_BLOCK, OVERSEAS_SOURCES
except ImportError:
    COMPLIANCE_BLOCK = []
    OVERSEAS_SOURCES = ()

# IP 相关关键词权重（对齐「小吴聊」AI/科技实战操盘手人设）
IP_KEYWORDS = {
    "AI": 3, "人工智能": 3, "大模型": 3, "Agent": 3, "智能体": 3, "模型": 2, "算力": 3,
    "芯片": 2, "GPU": 2, "机器人": 2, "自动驾驶": 2, "创业": 2, "副业": 2, "赚钱": 2,
    "变现": 2, "工具": 1, "自媒体": 2, "视频": 1, "直播": 1, "ETF": 2, "基金": 1,
    "投资": 1, "银行": 1, "电池": 2, "光伏": 2, "AI应用": 3, "裁员": 2, "就业": 2,
    "效率": 1, "NAS": 2, "Obsidian": 1, "公司": 1, "钱包": 2, "收入": 2, "市场": 1,
    "行业": 1, "产业": 1, "企业": 1, "增长": 1, "规模": 1,
}

# 标题冲击力：具体数字/问号/悬念/情绪词
IMPACT_RE = re.compile(
    r"\d+(?:\.\d+)?[亿万元%％倍]|[？?!！]|竟然|居然|秘密|真相|别|不再|反|离谱|爆|疯|狂|涨|跌|赚|亏|洗牌|创纪录"
)
# 对比冲突：从…到 / vs / 却 / 但 / 还是
CONTRAST_RE = re.compile(r"从.*到|vs|对比|还是|却|但|而|反")
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


def normalize_title(t):
    """去链接/序号/括号注解，压缩空白。"""
    t = re.sub(r"（\[链接\]\(.*?\)）", "", t)
    t = re.sub(r"^\d+[\.、．]\s*", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_radar(path):
    """解析热点雷达 md → [(title, source, link, rank)]"""
    rows = []
    source = ""
    for ln in open(path, encoding="utf-8"):
        ln = ln.rstrip("\n")
        if ln.startswith("## "):
            source = ln[3:].strip()
            continue
        m = re.match(r"\s*(\d+)[\.、．]\s*(.+?)(?:（\[链接\]\((.*?)\)）)?\s*$", ln)
        if m and source:
            rows.append((m.group(2).strip(), source, m.group(3) or "", int(m.group(1))))
    return rows


def score_item(title):
    ip = sum(IP_KEYWORDS.get(w, 0) for w in IP_KEYWORDS if w in title)
    impact = 2 if IMPACT_RE.search(title) else 0
    contrast = 1 if CONTRAST_RE.search(title) else 0
    return ip * 2 + impact + contrast


def suggest_view(title):
    if DECONSTRUCT_RE.search(title):
        return "【硬核拆解】"
    if DIALOGUE_RE.search(title):
        return "【商业对话】"
    return "【商业观察】"


def suggest_formulas(title):
    tags = [name for name, pat in FORMULA_TAGS.items() if re.search(pat, title)]
    return tags or ["身份代入"]


def main():
    ap = argparse.ArgumentParser(description="选题推荐器")
    ap.add_argument("--date", default="", help="热点雷达日期 YYYY-MM-DD（默认最新）")
    ap.add_argument("--top", type=int, default=5, help="候选数（默认 5）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

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

    # 合规初筛：命中关键词的条目不进候选（与采集器同规则）
    before = len(rows)
    rows = [r for r in rows if not any(kw in r[0] for kw in COMPLIANCE_BLOCK)]
    if len(rows) < before:
        print(f"⚠️ 合规初筛剔除 {before - len(rows)} 条", file=sys.stderr)

    # 评分 + 排序
    scored = sorted(
        ({"title": normalize_title(t), "source": s, "link": l, "rank": r,
          "score": score_item(t), "view": suggest_view(t), "formulas": suggest_formulas(t),
          "compliance": "海外源·需人工复核（国内可发布性）" if s in OVERSEAS_SOURCES else ""}
         for t, s, l, r in rows),
        key=lambda x: (-x["score"], x["rank"]),
    )

    # 跨源去重：同标题不同源计一次，加权 +3
    seen, deduped = {}, []
    for it in scored:
        key = re.sub(r"[\s：:，。、\-—]+", "", it["title"])[:14]
        if key in seen:
            seen[key]["score"] += 3
            seen[key]["source"] += " + " + it["source"]
            continue
        seen[key] = it
        deduped.append(it)
    deduped.sort(key=lambda x: (-x["score"], x["rank"]))

    picks = deduped[: args.top]
    today = datetime.now().strftime("%Y-%m-%d")
    month = today[:7]

    if args.json:
        print(json.dumps(picks, ensure_ascii=False, indent=2))
        return

    out_dir = os.path.join(MATERIALS_DIR, month)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{today}_选题推荐.md")

    lines = [
        f"# 🎯 选题推荐（{today}）",
        "",
        f"> 依据：{os.path.basename(radar_path)}｜排序：IP 相关度 + 标题冲击力 + 跨源热度",
        "> 用法：候选必须由用户（老板）拍板后进入 `topic` 态，禁止自动选第 1 条；海外源候选需人工复核国内可合规发布。",
        "> 📕 封面套路观察由采编在创作前按 `guizang-social-card-skill`/小红书对标补充。",
        "",
    ]
    for i, it in enumerate(picks, 1):
        lines += [
            f"## 候选 {i} ⭐热度 {it['score']:.1f}",
            f"- 主题方向：{it['title']}",
            f"- 命中热点：{it['source']}（rank {it['rank']}）",
            f"- 建议视角：{it['view']}",
            f"- 建议标题公式：{' + '.join(it['formulas'])}（对照 dbs-xhs-title 公式库）",
            f"- 合规：{it['compliance'] or '国内源·正常'}",
            "- 📕 封面套路观察：（采编补充：参考同类爆款封面的构图/钩子/配色）",
            f"- 原文链接：{it['link'] or '无'}",
            "",
        ]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"📁 选题推荐已落盘：{out_path}（{len(picks)} 个候选）")
    for it in picks:
        flag = "⚠️海外" if it["compliance"] else ""
        print(f"   ⭐{it['score']:.1f} [{it['view']}] {it['title']} ← {it['source']} {flag}")


if __name__ == "__main__":
    main()
