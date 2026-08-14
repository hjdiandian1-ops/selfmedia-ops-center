#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
去 AI 味机器初筛器（Anti AI-Flavor Checker）
=============================================
把 skills/anti-ai-flavor-skill/SKILL.md 中的结构级 AI 腔规则变成可执行检查：
句式壳（二元对比/阶段序列/本质断言/助手路线/弱化框架/虚假让步/展示型三拍）、
标点（正文引号/修辞破折号）、语气（老师式自问自答/替读者说话/空泛表扬）、
开头收尾（反问开场/报幕过渡/抒情过渡/对称收束/总结填充/无动机问句）。

规则来源（与 SKILL.md 一致）：
  [A] https://github.com/zero-click/avoid-ai-writing-zh
  [L] https://github.com/liuliu-66-create/ll-humanizer-zh
  [B] https://github.com/B1lli/remove-ai-flavor-writing-skill

词汇层（营销号套话/爹味/禁用开头）仍由 harsh_critic_score.py 负责，本脚本只做结构级，
避免重复扣分。

用法：
    python3 scripts/ai_flavor_check.py outputs/YYYY-MM-DD_主题名/
    python3 scripts/ai_flavor_check.py outputs/XXX/ --out outputs/XXX/ai_flavor_report.json

退出码：0 = PASSED/WARN（WARN 需人工复核）；1 = REJECTED（存在高风险 AI 腔，必须修改）。
"""
import argparse
import html
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compliance_check as CC  # noqa: E402  # 复用 platform_files（三平台 md/html 收集）

# 跨平台合并后按总次数重算等级（count_hits 的 per-platform 等级仅作初值）
ALWAYS_HIGH = {"formula_progression", "announcer_transition", "symmetry_closure", "belittle_reader"}
HIGH_AT = {
    "binary_shell": 3,
    "essence_claim": 3,
    "assistant_marker": 2,
    "fake_concession": 2,
    "teacher_qa": 3,
    "summary_filler": 2,
}


def _merged_severity(rule, count):
    if rule in ALWAYS_HIGH:
        return "high"
    if rule in HIGH_AT:
        return "high" if count >= HIGH_AT[rule] else "medium"
    return "medium"


# ---------- 规则定义 ----------

# 一、句式壳（结构级；计数规则通过 severity_fn 分级）

BINARY_SHELL = re.compile(r"不是.{0,24}?(?:而是|是)|与其说.{0,24}?(?:不如说|倒不如说)")
STAGE_SEQUENCE = re.compile(r"首先.{0,80}其次.{0,80}最后")
ESSENCE_CLAIM = re.compile(r"本质上|真正重要的是|核心在于|底层逻辑(?:是|在于|就是)?")
ASSISTANT_MARKER = re.compile(r"值得注意的是|不可否认的是|我们可以看到|总的来说|说白了|划重点")
WEAK_FRAME = re.compile(r"这次只看|答案很简单|废话不多说|直接上干货")
FAKE_CONCESSION = re.compile(r"(?:当然|固然|确实)重要[，,].{0,24}(?:但|但是|然而)|不可否认[，,].{0,24}(?:但|但是)")
TEACHER_QA = re.compile(r"(?:那么|所以)?[，,]?(?:这意味着什么|这意味着|答案是|答案很简单|原因很简单|原因在于|背后的逻辑(?:是|就是))")
PARALLEL_PREFIXES = ("不是", "没有", "能不能", "让每", "把每", "在每", "别让", "如果", "当每", "如何")

# 二、开头与收尾

ANNOUNCER_TRANSITION = re.compile(r"接下来[，,].{0,20}(?:从|通过|围绕).{0,20}(?:方面|维度|角度|三点|三个|几部分|来看|聊聊)|下面[，,]?(?:我)?(?:将|就|再).{0,12}(?:介绍|讲解|分析|展开)")
SYMMETRY_CLOSURE = re.compile(r"不是(?:结束|终点|告别|句号).{0,20}(?:而是|是)(?:开始|起点|序章|新)|(?:既是|是)(?:终点|结束|句号).{0,8}(?:也是|更是)(?:起点|开始)")
RHETORICAL_OPENING = re.compile(r"[？?].{0,8}(?:意味着什么|凭什么|你怎么看|难道|为什么)|那这对.{0,8}(?:意味着|说明)什么")
LYRIC_TRANSITION = re.compile(r"让我印象最深|最打动我|最让我感动|至今难忘|至今记忆犹新")
SUMMARY_FILLER = re.compile(r"由此可见|综上所述|总而言之")
NO_MOTIVATION_ENDING = re.compile(r"你准备好了吗|还在等什么|现在就开始吧|别犹豫了|心动不如行动")

# 三、语气与情绪（ll-humanizer）

SPEAK_FOR_READER = re.compile(r"你可能会想|相信你已经|你一定会(?:发现|觉得)|你能感受到|你会发现")
BELITTLE_READER = re.compile(r"连这个都不知道|如果你还不知道|说明你(?:落后|不行|out)")
EMPTY_PRAISE = re.compile(r"非常强大|非常优秀|表现令人印象深刻|令人印象深刻|极为出色")
REPORT_ANALYSIS = re.compile(r"体现了|反映了|印证了")
QUOTE_OPEN = re.compile(r"[“‘「『《]")
DASH_RHETORIC = "——"


def _snippet(text, match, width=42):
    start = max(0, match.start() - width // 3)
    end = min(len(text), match.end() + width - width // 3)
    snip = text[start:end].replace("\n", "␤")
    prefix = "…" if start else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{snip}{suffix}"


def _parallel_run(text):
    """连续 ≥4 行以同一 2 字前缀开头 → 排比结构；返回最长连续行数。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    best, run, prev = 0, 0, None
    for ln in lines:
        head = ln[:2]
        if head and head == prev:
            run += 1
        else:
            run = 1
            prev = head
        best = max(best, run)
    return best


def _strip_frontmatter(text):
    return re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.S)


def _platform_texts(output_dir):
    """复用 compliance 的三平台收集逻辑，返回 {平台: 去 frontmatter 的拼接正文}。"""
    out = {}
    for plat, text in CC.platform_files(output_dir).items():
        out[plat] = _strip_frontmatter(text)
    return out


def check(text):
    """对单平台正文返回命中列表：[{rule, severity, source, pattern, count, examples}]。"""
    hits = []

    def add(rule, severity, source, pattern, count, examples, suggestion):
        if count:
            hits.append({
                "rule": rule, "severity": severity, "source": source,
                "pattern": pattern, "count": count,
                "examples": examples[:3], "suggestion": suggestion,
            })

    def count_hits(regex, label, source, high_at, suggestion, severity="medium", min_count=1):
        ms = list(regex.finditer(text))
        if len(ms) < min_count:
            return
        n = len(ms)
        sev = "high" if n >= high_at else severity
        examples = [_snippet(text, m) for m in ms]
        add(label, sev, source, regex.pattern, n, examples, suggestion)

    head = text.strip()[:80]

    # 句式壳
    count_hits(BINARY_SHELL, "binary_shell", "[B][A]", 3,
               "「不是 A 而是 B」全文 ≤2 次；≥3 次为二元对比模板，改成直陈事实。")
    ms = list(STAGE_SEQUENCE.finditer(text))
    if ms:
        add("formula_progression", "high", "[A][B]", STAGE_SEQUENCE.pattern, len(ms),
            [_snippet(text, m) for m in ms],
            "「首先…其次…最后」三连是 AI 分点腔，改写为按内容权重排序的自然段落。")
    count_hits(ESSENCE_CLAIM, "essence_claim", "[B]", 3,
               "「本质上/真正重要的是/核心在于」1 次 WARN，≥3 次 REJECTED；直接说结论。")
    count_hits(ASSISTANT_MARKER, "assistant_marker", "[B][A]", 2,
               "「值得注意的是/总的来说/我们可以看到」是报幕词，删掉后句子依然成立就该删。")
    count_hits(WEAK_FRAME, "weak_frame", "[B]", 999,
               "「答案很简单/这次只看」高频出现显得在安排读者，保留最自然的 1 处即可。")
    count_hits(FAKE_CONCESSION, "fake_concession", "[A]", 2,
               "「X 当然重要，但 Y 才是」虚假让步三拍 1 次 WARN，≥2 次 REJECTED；改成有事实依据的转折。")
    count_hits(TEACHER_QA, "teacher_qa", "[L]", 3,
               "老师式自问自答（提问后立刻给答案）≤2 次；把问题留给读者思考。")
    parallel = _parallel_run(text)
    if parallel >= 4:
        add("parallel_structure", "medium", "[A]", f"连续同前缀行 ≥{parallel} 行",
            parallel, [f"连续 {parallel} 行以相同前缀开头"], "排比连续 4 次以上建议拆成有信息差的分句。")

    # 开头与收尾
    if RHETORICAL_OPENING.search(head):
        m = RHETORICAL_OPENING.search(head)
        add("rhetorical_opening", "medium", "[A]", RHETORICAL_OPENING.pattern, 1,
            [_snippet(head, m)], "开头反问是 AI 常用钩子，改为直接抛事实/数字。")
    ms = list(ANNOUNCER_TRANSITION.finditer(text))
    if ms:
        add("announcer_transition", "high", "[A]", ANNOUNCER_TRANSITION.pattern, len(ms),
            [_snippet(text, m) for m in ms],
            "报幕式过渡（接下来我们从…来看）是内容外包壳，直接删掉。")
    ms = list(SYMMETRY_CLOSURE.finditer(text))
    if ms:
        add("symmetry_closure", "high", "[A]", SYMMETRY_CLOSURE.pattern, len(ms),
            [_snippet(text, m) for m in ms],
            "「不是结束，而是开始」类对称收束是 AI 升华腔，用具体判断收尾。")
    count_hits(LYRIC_TRANSITION, "lyric_transition", "[A]", 999,
               "「让我印象最深的是」情绪预告，用具体细节替代。")
    count_hits(SUMMARY_FILLER, "summary_filler", "[A]", 2,
               "「由此可见/综上所述」总结填充 ≤1 次；结尾给判断或行动增量。")
    count_hits(NO_MOTIVATION_ENDING, "no_motivation_ending", "[B]", 999,
               "「你准备好了吗/还在等什么」无动机问句，行动号召需要前文证据支撑。")

    # 语气与情绪
    count_hits(SPEAK_FOR_READER, "speak_for_reader", "[L]", 999,
               "「你可能会想/相信你已经发现」替读者说话，改说自己看到什么。")
    ms = list(BELITTLE_READER.finditer(text))
    if ms:
        add("belittle_reader", "high", "[L]", BELITTLE_READER.pattern, len(ms),
            [_snippet(text, m) for m in ms],
            "贬低读者位置（连这个都不知道）是爹味底线，必须删除。")
    count_hits(EMPTY_PRAISE, "empty_praise", "[L]", 999,
               "「非常强大/令人印象深刻」空泛表扬，必须带具体指标或场景。")
    count_hits(REPORT_ANALYSIS, "report_analysis", "[L]", 999,
               "「体现了/反映了/印证了」把真实反应写成报告式分析，≥3 次需改写。", min_count=3)

    # 标点
    q = len(QUOTE_OPEN.findall(text))
    if q >= 4:
        add("prose_quotes", "medium", "[L]", "正文引号(开引号)计数", q,
            [f"正文出现 {q} 处引号/书名号（真实人物原话除外）"], "AI 爱用引号造词；真实引语允许，强调性引号删除。")
    dash_n = text.count(DASH_RHETORIC)
    if dash_n >= 2:
        add("dash_rhetoric", "medium", "[L]", DASH_RHETORIC, dash_n,
            [f"正文出现 {dash_n} 处修辞破折号"], "破折号作修辞标点禁用；技术标识中的连字符例外。")

    return hits


def run(output_dir):
    """返回整包报告 dict。"""
    texts = _platform_texts(output_dir)
    all_hits = []
    for plat, text in texts.items():
        for h in check(text):
            h["platform"] = plat
            all_hits.append(h)

    # 按 rule 聚合跨平台（同一规则三平台各 1 次 = 3 次，合并计数更严格）
    merged = {}
    for h in all_hits:
        k = h["rule"]
        if k not in merged:
            merged[k] = dict(h)
            merged[k]["count"] = 0
            merged[k]["platforms"] = []
            merged[k]["examples"] = []
        m = merged[k]
        m["count"] += h["count"]
        if h["platform"] not in m["platforms"]:
            m["platforms"].append(h["platform"])
        m["examples"] = (m["examples"] + h["examples"])[:3]
    for h in merged.values():
        h["severity"] = _merged_severity(h["rule"], h["count"])
    hits = sorted(merged.values(), key=lambda x: (x["severity"] != "high", -x["count"]))

    highs = [h for h in hits if h["severity"] == "high"]
    mediums = [h for h in hits if h["severity"] == "medium"]
    verdict = "REJECTED" if highs else ("WARN" if mediums else "PASSED")

    return {
        "output_dir": output_dir,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "verdict": verdict,
        "summary": {
            "platforms": list(texts.keys()),
            "high": len(highs),
            "medium": len(mediums),
            "total_hits": sum(h["count"] for h in hits),
        },
        "hits": hits,
        "manual_review": [
            "展示型三拍（对仗短句+点评）与均匀段落形状机器不判定，需人工复核。",
            "引号/破折号命中需人工确认是否属于真实引语/技术标识例外。",
            "REJECTED 退回对应主编重写；WARN 由资深校对排版逐条复核后写入 评分报告.md。",
        ],
        "rules_note": "规则来源：[A] zero-click/avoid-ai-writing-zh ｜ [L] liuliu-66-create/ll-humanizer-zh ｜ "
                      "[B] B1lli/remove-ai-flavor-writing-skill（详见 skills/anti-ai-flavor-skill/SKILL.md）",
    }


def main():
    ap = argparse.ArgumentParser(description="去 AI 味机器初筛")
    ap.add_argument("output_dir", help="产出目录 outputs/YYYY-MM-DD_主题名/")
    ap.add_argument("--out", help="将 JSON 报告落盘到指定路径")
    args = ap.parse_args()

    report = run(args.output_dir)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("🧼 去 AI 味机器初筛（结构级，需人工复核例外）")
    print("=" * 60)
    if not report["summary"]["platforms"]:
        print("⚠️ 未找到任何平台成稿（小红书/公众号/短视频 下的 *.md / *.html）")
    for h in report["hits"]:
        icon = {"high": "🛑", "medium": "⚠️"}[h["severity"]]
        print(f"{icon} [{h['rule']}]（{h['source']}）×{h['count']} "
              f"平台:{'、'.join(h['platforms'])}")
        for ex in h["examples"][:2]:
            print(f"    例：{ex}")
    print("-" * 60)
    s = report["summary"]
    label = {"PASSED": "✅ PASSED", "WARN": "⚠️ WARN", "REJECTED": "🛑 REJECTED"}[report["verdict"]]
    print(f"命中 {s['total_hits']} 处（high {s['high']} / medium {s['medium']}）→ {label}")
    print("⚠️ 机器只负责可数规则：展示型三拍/段落形状/引号破折号例外需人工复核。")
    sys.exit(0 if report["verdict"] in ("PASSED", "WARN") else 1)


if __name__ == "__main__":
    main()
