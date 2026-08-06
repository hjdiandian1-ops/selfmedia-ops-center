#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Harsh Critic 双轨评分机器初评器 (Harsh Critic v2 · 可复算实现)
=============================================================
把 harsh-critic-skill v2 的评分公式变成可执行代码，作为质检环节的"机器初评"：
先跑本脚本得机器分与逐项明细，再由资深校对排版人工复核每条证据（Skill 负责判断力，脚本负责可数性）。

公式（对齐 skills/harsh-critic-skill/SKILL.md）：
    总分 = 正向质量分（0~60）+ 负向得分（40 − 扣分，最低 0）
    判定：≥85 → PASSED；<85 → REJECTED（输出逐项失分明细）

用法：
    python3 scripts/harsh_critic_score.py outputs/2026-08-04_主题名/
    python3 scripts/harsh_critic_score.py outputs/XXX/ --materials materials/2026-08/XXX素材包.md --out outputs/XXX/harsh_report.json

退出码：0 = PASSED；1 = REJECTED。仅依赖标准库。
"""
import argparse
import json
import os
import re
import sys

# 复用素材契约校验器的解析逻辑（同目录模块）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_materials_contract as VMC  # noqa: E402

# ---------- 启发式规则（与 SKILL.md 细则一一对应） ----------

# 正向·数据密度：每处具体数字 3 分，上限 15（复用契约校验器 NUMBER_TOKEN）
# 正向·真实感：第一人称 + 真实项目/工具/型号名
FIRST_PERSON = re.compile(r"[我咱本]")
REAL_NAME = re.compile(
    r"\b(?:NAS|n8n|ComfyUI|MoneyPrinter|Remotion|FLUX|DALL[ -]?E|Midjourney|ChatGPT|Claude|Gemini|"
    r"RSSHub|Playwright|FastAPI|Docker|Postgres|Redis|Kubernetes|微信|小红书|抖音|视频号)\b|"
    r"\b[A-Za-z][A-Za-z0-9\-]*(?:\s*[A-Za-z0-9]+)*\s*\d+(?:\.\d+)?\s*(?:型|代|版|G|GB|TB)\b"
)
# 正向·Hook 冲击力（六维的机器可算近似）：
#   A 开头非禁用句式；B 首句含数字或问号；C 首句 ≤40 字(口播友好)；D 标题含数字/问号/悬念词；
#   E 开头可信度（首段含真实项目/第一人称/数字）；F 标题承诺与正文匹配
HOOK_SUSPENSE = re.compile(r"[？?!！]|\d|竟然|居然|秘密|真相|别|别再|没想到|只要|免费|月入|一年|实测")
HOOK_DIMS = 6  # 每过 1 维 2 分，6 维封顶 10 分

# 负向·孤行：段落间独立的 1-3 汉字短行（公众号排版审美扣分）
ORPHAN_LINE = re.compile(r"\n\n\s*([\u4e00-\u9fff]{1,3})\s*\n\n")


def draft_texts(drafts):
    """{plat: 拼接后的正文(去 frontmatter)}"""
    out = {}
    for plat, paths in drafts.items():
        parts = []
        for p in paths:
            t = VMC.read_text(p)
            t = re.sub(r"^---\s*\n.*?\n---\s*\n", "", t, flags=re.S)
            parts.append(t)
        out[plat] = "\n".join(parts)
    return out


def first_sentence(text):
    m = re.search(r"([^\n。！？!?]+[。！？!?]?)", text.strip())
    return (m.group(1).strip() if m else text.strip())[:200]


def first_line(text):
    for ln in text.splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            return ln
    return ""


def machine_hook_breakdown(text):
    """机器 6 维 Hook 初筛：返回 (通过维度列表, 得分[0-10])。
    仅供初筛；最终 6 维判定与证据必须由人工写入 评分报告.md。
    """
    title = first_line(text)
    head = first_sentence(first_line(text) + " " + text[:300])
    norm_body = VMC.normalize(text)
    passed = []

    # A 开头非禁用句式
    if not any(re.search(p, head) for p in VMC.BANNED_OPENINGS):
        passed.append("A-非禁用开头")
    # B 首句含数字/问号
    if re.search(r"\d|[?？!！]", head[:60]):
        passed.append("B-数字/悬念")
    # C 口播友好短句
    if len(head) <= 40:
        passed.append("C-口播短句")
    # D 标题含悬念词
    if HOOK_SUSPENSE.search(title):
        passed.append("D-标题悬念")
    # E 开头可信度（机器近似：前 120 字有真实项目/第一人称/数字）
    if REAL_NAME.search(head[:120]) or FIRST_PERSON.search(head[:120]) or re.search(r"\d", head[:120]):
        passed.append("E-开头可信度")
    # F 标题承诺与正文匹配（标题关键数字/关键词出现在正文）
    title_nums = VMC.NUMBER_TOKEN.findall(title)
    title_kws = [w for w in re.findall(r"[\u4e00-\u9fa5A-Za-z]{2,}", title)
                 if w not in ("标题", "正文")]
    matched = any(n.replace(" ", "") in norm_body for n in title_nums) or \
              any(k in norm_body for k in title_kws[:3])
    if matched:
        passed.append("F-承诺匹配")

    return passed, min(10, len(passed) * 2)


def main():
    ap = argparse.ArgumentParser(description="Harsh Critic 双轨评分机器初评")
    ap.add_argument("output_dir", help="产出目录 outputs/YYYY-MM-DD_主题名/")
    ap.add_argument("--materials", help="显式指定素材包路径")
    ap.add_argument("--out", help="将 JSON 报告落盘到指定路径")
    args = ap.parse_args()

    results = []  # (level, code, message)

    def report(level, code, msg):
        results.append({"level": level, "code": code, "message": msg})

    # ---------- 素材与成稿解析（复用契约校验器） ----------
    pack_path = VMC.find_material_pack(args.output_dir, args.materials)
    items, schema_complete = [], False
    if pack_path:
        items, schema_complete = VMC.parse_materials(VMC.read_text(pack_path))
    drafts = VMC.find_drafts(args.output_dir)
    texts = draft_texts(drafts)
    if not drafts:
        report("FAIL", "E0-no-draft", "未找到任何平台成稿（小红书/公众号/短视频 下的 *.md）")
        print(json.dumps({"score": 0, "verdict": "REJECTED", "results": results},
                         ensure_ascii=False, indent=2))
        sys.exit(1)

    all_norm = VMC.normalize("".join(texts.values()))

    # ---------- 正向质量分（60） ----------
    pos = {}

    # 1. 素材引用率 20 分（跨平台：核心素材在任一平台被实质引用即算）
    core = [it for it in items if it["priority"] == "核心"] if schema_complete else []
    consumed = 0
    decayed = []
    for it in core:
        hit = False
        if it["tokens"]:
            hit = any(re.search(re.escape(t.replace(" ", "")), all_norm.replace(" ", "")) for t in it["tokens"])
        if not hit and it.get("kw") and len(it["kw"]) >= 2:
            hit = it["kw"] in all_norm
        if not hit and it["norm"]:
            hit = it["norm"] in all_norm
        if hit:
            consumed += 1
        else:
            decayed.append(it["id"])
    rate = consumed / len(core) if core else 0.0
    pos["素材引用率"] = round(rate * 20, 1)
    if core:
        report("PASS" if rate >= 1.0 else "FAIL", "P1-rate",
               f"素材引用率 {consumed}/{len(core)}={rate:.0%} → {pos['素材引用率']}/20" +
               (f"，衰减素材：{decayed}" if decayed else ""))

    # 2. 数据密度 15 分
    num_count = sum(len(VMC.NUMBER_TOKEN.findall(t)) for t in texts.values())
    pos["数据密度"] = min(15, num_count * 3)
    report("PASS", "P2-density", f"具体数字 {num_count} 处 → {pos['数据密度']}/15")

    # 3. 真实感 15 分
    real_hits = 0
    for t in texts.values():
        if FIRST_PERSON.search(t):
            real_hits += 1
        real_hits += len(REAL_NAME.findall(t))
    pos["真实感"] = min(15, real_hits * 5)
    report("PASS", "P3-realness", f"第一人称/真实项目名/型号 {real_hits} 处 → {pos['真实感']}/15")

    # 4. Hook 冲击力 10 分（机器 6 维初筛；最终证据人工复核）
    hook_pts = 0
    hook_detail = []
    for plat, t in texts.items():
        if plat == "短视频":
            continue
        dims, pts = machine_hook_breakdown(t)
        hook_detail.append(f"{plat}:{len(dims)}维")
        hook_pts = max(hook_pts, pts)
    pos["Hook冲击力"] = hook_pts
    report("PASS" if hook_pts >= 4 else "FAIL", "P4-hook",
           f"Hook 冲击力（{'；'.join(hook_detail)}）→ {hook_pts}/10"
           "（机器 6 维初筛，需人工复核并写入评分报告.md）")

    pos_total = round(sum(pos.values()), 1)

    # ---------- 负向扣分（40） ----------
    neg = 0
    # 1. 营销号套话 -20/处
    for g in VMC.GREASY_PHRASES:
        cnt = sum(t.count(g) for t in texts.values())
        if cnt:
            neg += 20 * cnt
            report("FAIL", "N1-greasy", f"营销号套话「{g}」×{cnt} → -{20*cnt}")
    # 2. 虚构案例 -30/处（AI推断 素材被当作事实引用）
    ai_items = [it for it in items if it["source_type"] == "AI推断"]
    for it in ai_items:
        if it.get("norm") and it["norm"] in all_norm:
            neg += 30
            report("FAIL", "N2-fake", f"虚构案例：AI推断 素材「{it['text']}…」被当事实引用 → -30")
    # 3. AI 腔开头 -15/篇
    for plat, t in texts.items():
        body = re.sub(r"^#+ .*$", "", t, flags=re.M).strip()[:150]
        for pat in VMC.BANNED_OPENINGS:
            if re.search(pat, body):
                neg += 15
                report("FAIL", "N3-ai-open", f"[{plat}] 命中禁用开头 /{pat}/ → -15")
                break
    # 4. 孤行 -10/处（公众号排版）
    for plat, t in texts.items():
        if plat == "公众号":
            orphans = ORPHAN_LINE.findall(t)
            if orphans:
                neg += 10 * len(orphans)
                report("FAIL", "N4-orphan", f"[公众号] 孤行 {len(orphans)} 处（{orphans[:3]}…）→ -{10*len(orphans)}")
    # 5. 素材来源不可溯源（P0：真实数据无 URL / 链接待补） -15/处
    if items:
        for code, msg in VMC.material_url_issues(items):
            neg += 15
            report("FAIL", code, f"{msg} → -15")

    neg_total = min(40, neg)
    total = round(pos_total + (40 - neg_total), 1)
    verdict = "PASSED" if total >= 85 else "REJECTED"

    # ---------- 报告 ----------
    report_doc = {
        "output_dir": args.output_dir,
        "materials": pack_path,
        "scored_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pos": pos, "pos_total": pos_total,
        "neg_deducted": neg_total, "neg_raw": neg,
        "score": total, "verdict": verdict,
        "manual_review": "机器分为初筛：人工必须复核 Hook 六维、事实来源与视觉排版，"
                         "并在 outputs/<job_id>/评分报告.md 逐条写出证据。",
        "results": results,
    }
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report_doc, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("🛑 Harsh Critic 机器初评（v2 双轨，需人工复核证据）")
    print("=" * 60)
    for r in results:
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[r["level"]]
        print(f"{icon} [{r['code']}] {r['message']}")
    print("-" * 60)
    print(f"正向质量分：{pos_total}/60（{pos}）")
    print(f"负向扣分：-{neg_total}/40（原始扣 {neg}）")
    print(f"总分：{total}/100 → {'✅ PASSED' if verdict == 'PASSED' else '❌ REJECTED'}（阈值 85）")
    print("⚠️ 机器分为初筛：请按 SKILL.md 人工复核 Hook 六维/事实来源/视觉，并在 评分报告.md 逐条写证据。")

    sys.exit(0 if verdict == "PASSED" else 1)


if __name__ == "__main__":
    main()
