#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容合规审核器（机器初筛）
==========================
发布前的合规硬门槛：按平台（小红书/抖音/公众号）检查广告法绝对化用语、
站外导流、敏感行业（医疗/金融/教育）、标题党诱导、AI 生成内容标识等。

规则来源：
  - 内置规则为初版词库（详见 research/平台内容合规规范.md 的官方依据）
  - 可外挂词库：data/compliance/words/*.txt（每行一个关键词/正则），
    ad.txt 全平台；xhs.txt / douyin.txt / gzh.txt 按平台加载

用法：
    python3 scripts/compliance_check.py outputs/2026-08-14_主题名/
    python3 scripts/compliance_check.py outputs/XXX/ --out outputs/XXX/compliance_report.json

退出码：0 = PASSED/WARN（可发布，WARN 需人工复核）；1 = REJECTED（存在高风险项，禁止发布）。
"""
import argparse
import glob
import html
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
WORDS_DIR = os.path.join(ROOT, "data", "compliance", "words")

# ---------- 内置规则（初版；外挂词库会被追加） ----------

# 《广告法》绝对化用语（组合词，避免“第一”“最”裸词误报）
AD_ABSOLUTE_WORDS = [
    "全网第一", "全国第一", "全球第一", "行业第一", "销量第一", "排名第一",
    "第一品牌", "第一人", "最好用", "最好", "最佳", "最优", "最低价", "最高级",
    "顶级", "国家级", "世界级", "宇宙级", "史无前例", "空前绝后", "独一无二",
    "绝无仅有", "唯一", "首家", "首个", "首款", "首创", "极致", "绝对",
    "万能", "100%有效", "百分之百有效", "包治", "根治",
]

# 特殊行业功效/承诺类（个人账号无资质发布 = 高风险）
MEDICAL_CLAIMS = [
    "治疗", "治愈", "根治", "抗癌", "防癌", "药到病除", "降血压", "降血糖",
    "丰胸", "壮阳", "脱发治疗", "祛斑", "祛痘", "医美效果", "三天见效", "七天见效",
    "药方", "医美", "诊断", "偏方", "秘方", "降尿酸", "降血脂",
]
FINANCE_CLAIMS = [
    "稳赚", "保本", "无风险", "收益保证", "荐股", "股票推荐", "内幕消息",
    "代操盘", "理财导师", "带你赚钱", "躺赚", "日入过千", "月入过万",
    "投资建议", "购房建议", "跟着买", "内部渠道",
]
EDUCATION_CLAIMS = [
    "包过", "保过", "代考", "押题必中", "证书挂靠", "不过退款", "考试答案",
]
SUPERSTITION_WORDS = ["算命", "转运", "消灾", "改运", "风水", "灵符", "法事"]

# 站外导流 / 联系方式（小红书/抖音红线；公众号中风险）
CONTACT_PATTERNS = [
    r"微信[号聊]?[:：]?\s*[a-zA-Z][a-zA-Z0-9_-]{4,}",
    r"加\s*V", r"私信领取", r"评论区扣\s*\d+", r"扫码领取", r"扫二维码",
    r"1[3-9]\d{9}", r"QQ群[:：]?\s*\d{5,}", r"淘宝搜索", r"点击链接领取",
]

# 境外未准入社交平台与链接（国内全平台高风险红线：X/Twitter/YouTube/Telegram/Discord等）
OVERSEAS_BLOCKED_PATTERNS = [
    r"(?:https?://)?(?:www\.)?(?:x\.com|twitter\.com|t\.co|youtube\.com|youtu\.be|t\.me|telegram\.org|telegram\.me|discord\.gg|discord\.com/invite|facebook\.com|fb\.watch|instagram\.com|threads\.net)\b[^\s\"'<>]*",
    r"(?:推特|Twitter|油管|YouTube|Telegram|电报群|Discord|Instagram|Threads)\s*(?:链接|地址|主页|账号|关注|@)",
    r"X\s*@\w+",
]

# 标题党 / 诱导分享（低-中风险，但易触发平台治理）
CLICKBAIT_WORDS = [
    "震惊", "删前速看", "马上删除", "不转不是", "转了才", "紧急通知",
    "速看", "千万别错过", "看一次少一次", "内幕曝光",
]

# AI 生成内容标识（2025-09-01《人工智能生成合成内容标识办法》）
AI_NOTICE_WORDS = ["AI生成", "AI 生成", "AI辅助", "AI 辅助", "由AI生成", "人工智能生成", "AI创作", "AI 创作"]


def load_external_words():
    """加载 data/compliance/words/*.txt（每行一个词），返回 {platform: [words]}。"""
    out = {"ad": [], "xhs": [], "douyin": [], "gzh": []}
    if not os.path.isdir(WORDS_DIR):
        return out
    for f in os.listdir(WORDS_DIR):
        stem = os.path.splitext(f)[0]
        if stem not in out:
            continue
        p = os.path.join(WORDS_DIR, f)
        with open(p, encoding="utf-8") as fh:
            for ln in fh:
                w = ln.strip()
                if w and not w.startswith("#"):
                    out[stem].append(w)
    return out


def normalize(text):
    return re.sub(r"[\s*`#>「」“”\"'，。、：:；;！!？?（）()\[\]【】—\-…·]+", "", text)


def strip_html(text):
    text = re.sub(r"<script.*?</script>", "", text, flags=re.S)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", " ", text))


def platform_files(target_path):
    """按平台收集待审文本：支持单文件、平台子目录或通用目录。"""
    found = {}
    if os.path.isfile(target_path):
        try:
            with open(target_path, encoding="utf-8") as f:
                t = f.read()
            if target_path.endswith((".html", ".htm")):
                t = strip_html(t)
            # 智能推断平台
            plat = "通用"
            for p in ("小红书", "公众号", "短视频", "抖音"):
                if p in target_path or f"platform: {p}" in t:
                    plat = p
                    break
            return {plat: t}
        except OSError:
            return {}

    # 目录扫描：优先按小红书/公众号/短视频平台子目录扫描
    for plat in ("小红书", "公众号", "短视频", "抖音"):
        texts = []
        for ext in ("*.md", "*.html", "*.htm"):
            for p in glob.glob(os.path.join(target_path, plat, ext)):
                try:
                    with open(p, encoding="utf-8") as f:
                        t = f.read()
                except OSError:
                    continue
                if ext != "*.md":
                    t = strip_html(t)
                texts.append(t)
        if texts:
            found[plat] = "\n".join(texts)

    # 兜底：若没有标准平台子目录，直接扫描该目录下所有 md / html 文件
    if not found and os.path.isdir(target_path):
        generic_texts = []
        for root_dir, _, files in os.walk(target_path):
            for fname in files:
                if fname.endswith((".md", ".html", ".htm")):
                    p = os.path.join(root_dir, fname)
                    try:
                        with open(p, encoding="utf-8") as f:
                            t = f.read()
                        if fname.endswith((".html", ".htm")):
                            t = strip_html(t)
                        generic_texts.append(t)
                    except OSError:
                        continue
        if generic_texts:
            found["通用"] = "\n".join(generic_texts)

    return found


def check_platform(platform, text, words, checks):
    """按平台跑规则，追加 checks。"""
    if platform == "短视频":
        platform = "抖音"  # 短视频成品对应抖音发布，按抖音红线审核
    norm = normalize(text)

    def hit(pattern):
        return re.search(pattern, norm)

    # 广告法绝对化用语（全平台高风险）
    for w in words["ad"] + AD_ABSOLUTE_WORDS:
        if w in norm:
            checks.append({
                "rule": "ad_absolute", "platform": platform, "severity": "high",
                "keyword": w, "message": "广告法绝对化用语，涉嫌违反《广告法》第九条",
                "evidence": _snippet(text, w),
            })

    # 特殊行业（高）
    for cat, words_list, label in (
        ("medical", MEDICAL_CLAIMS, "医疗功效宣称"),
        ("finance", FINANCE_CLAIMS, "金融收益承诺/荐股"),
        ("education", EDUCATION_CLAIMS, "教育考试承诺"),
    ):
        for w in words_list:
            if w in norm:
                checks.append({
                    "rule": cat, "platform": platform, "severity": "high",
                    "keyword": w,
                    "message": f"{label}：个人账号无资质发布高风险内容，需删改或取得相应资质",
                    "evidence": _snippet(text, w),
                })

    # 站外导流 / 联系方式（小红书/抖音高，公众号中）
    sev = "high" if platform in ("小红书", "抖音") else "medium"
    for pat in CONTACT_PATTERNS:
        m = re.search(pat, text)
        if m:
            checks.append({
                "rule": "contact_leak", "platform": platform, "severity": sev,
                "keyword": m.group(0)[:30],
                "message": "站外导流/联系方式：" + ("平台红线，易限流" if sev == "high" else "公众号内建议避免站外链接"),
                "evidence": _snippet(text, m.group(0)),
            })

    # 境外未准入社交平台与链接（国内全平台强制高风险红线：X/Twitter/YouTube等）
    for pat in OVERSEAS_BLOCKED_PATTERNS:
        m = re.search(pat, text, re.I)
        if m:
            checks.append({
                "rule": "overseas_blocked_platform", "platform": platform, "severity": "high",
                "keyword": m.group(0)[:40],
                "message": "出现境外未准入社交平台/链接（X/Twitter/YouTube等），国内发布会触发平台合规拦截与限流封号，请替换为开源仓库/官方文档/通用社区实测描述",
                "evidence": _snippet(text, m.group(0)),
            })

    # 标题党 / 诱导
    for w in CLICKBAIT_WORDS:
        if w in norm:
            checks.append({
                "rule": "clickbait", "platform": platform, "severity": "medium",
                "keyword": w, "message": "标题党/诱导分享表述，平台治理易降权",
                "evidence": _snippet(text, w),
            })

    # 迷信用语（中风险，平台治理敏感）
    for w in SUPERSTITION_WORDS:
        if w in norm:
            checks.append({
                "rule": "superstition", "platform": platform, "severity": "medium",
                "keyword": w, "message": "迷信/风水算命类表述，平台治理敏感，建议删除",
                "evidence": _snippet(text, w),
            })

    # 平台专属违禁词
    key = {"小红书": "xhs", "抖音": "douyin", "公众号": "gzh"}.get(platform, "gzh")
    for w in words.get(key, []):
        if w in norm:
            checks.append({
                "rule": "platform_wordlist", "platform": platform, "severity": "medium",
                "keyword": w, "message": f"命中{platform}合规词库（外挂 data/compliance/words/{key}.txt）",
                "evidence": _snippet(text, w),
            })

    # AI 生成内容标识（建议）
    if not any(w in text for w in AI_NOTICE_WORDS):
        checks.append({
            "rule": "ai_notice", "platform": platform, "severity": "warn",
            "keyword": "AI生成标识",
            "message": "建议标注 AI 生成/辅助声明（2025-09-01《人工智能生成合成内容标识办法》）",
            "evidence": "全文未发现 AI 生成声明",
        })


def _snippet(text, kw, width=40):
    i = text.find(kw)
    if i < 0:
        return ""
    start = max(0, i - width)
    return text[start:i + len(kw) + width].replace("\n", " ")[:120]


def run(output_dir, out_path=None):
    texts = platform_files(output_dir)
    words = load_external_words()
    checks = []
    for platform, text in texts.items():
        check_platform(platform, text, words, checks)

    # 内置词库与外挂词库重叠时去重（同一规则+平台+关键词只报一次）
    seen, unique = set(), []
    for c in checks:
        key = (c["rule"], c["platform"], c["keyword"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)
    checks = unique

    highs = [c for c in checks if c["severity"] == "high"]
    mediums = [c for c in checks if c["severity"] == "medium"]
    warns = [c for c in checks if c["severity"] == "warn"]
    verdict = "REJECTED" if highs else ("WARN" if mediums else ("PASSED" if warns else "PASSED"))
    report = {
        "verdict": verdict,
        "checks": checks,
        "summary": {
            "high": len(highs), "medium": len(mediums), "warn": len(warns),
            "platforms": list(texts.keys()),
        },
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rules_note": "机器初筛，高风险项禁止发布；中风险人工复核；词库见 data/compliance/words/",
    }
    if not out_path:
        if os.path.isdir(output_dir):
            out_path = os.path.join(output_dir, "compliance_report.json")
        else:
            out_path = os.path.join(os.path.dirname(output_dir) or ".", "compliance_report.json")
    dir_name = os.path.dirname(out_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def main():
    ap = argparse.ArgumentParser(description="内容合规审核器")
    ap.add_argument("output_dir", help="产出目录 outputs/YYYY-MM-DD_主题名/")
    ap.add_argument("--out", help="报告输出路径（默认 outputs/<dir>/compliance_report.json）")
    args = ap.parse_args()
    report = run(args.output_dir, args.out)
    s = report["summary"]
    print(f"合规审核：{report['verdict']} ｜ 高 {s['high']} / 中 {s['medium']} / 建议 {s['warn']}"
          f" ｜ 平台 {','.join(s['platforms']) or '未找到待审文本'}")
    for c in report["checks"][:8]:
        print(f"  - [{c['severity']}] {c['platform']}｜{c['message']}（{c['keyword']}）")
    sys.exit(1 if report["verdict"] == "REJECTED" else 0)


if __name__ == "__main__":
    main()
