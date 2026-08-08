#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
素材契约校验器 (Materials Contract Validator)
==============================================
用途：机器校验「素材包 → 成稿」契约，检出素材衰减、虚构引用、AI 腔开头等问题。
配套：workflows/自媒体运营工厂.md 的成稿契约 + skills/harsh-critic-skill v2 第零步。

用法：
    python3 scripts/validate_materials_contract.py outputs/2026-08-04_主题名/
    python3 scripts/validate_materials_contract.py outputs/XXX/ --materials materials/2026-08/XXX素材包.md --strict

退出码：0 = 通过（允许有 WARN）；1 = 存在 FAIL。
仅依赖标准库。
"""
import argparse
import glob
import json
import os
import re
import sys

# ---------- 规则常量 ----------

BANNED_OPENINGS = [
    r"在过去[一二三四五六七八九十\d]+年",
    r"随着.*(飞速发展|快速发展|的浪潮|的兴起)",
    r"市场上出现了成千上万",
    r"近年来[，,]?越来越多",
    r"在当今.*时代",
]

GREASY_PHRASES = [
    "听我一句劝", "别再拿", "当玩具", "赶紧关掉",
    "教你", "都是割韭菜", "不可否认的是", "月入几万", "躺赚",
]

# 具体数字判定：数字 + 明确单位（排除 年/月 等易误报单位）
NUMBER_TOKEN = re.compile(r"\d+(?:\.\d+)?\s*(?:元|%|％|倍|万|亿|单|条|款|秒|分钟|小时|天|周|篇|张|套|次|人|家|台|个|块|GB|MB|TB|token|Token)", re.I)

# 来源链接强制（P0：真实数据必须可溯源）
URL_RE = re.compile(r"https?://[^\s)）>]+")
PLACEHOLDER_SOURCE = re.compile(r"(链接|来源|出处|URL|url)?\s*(待补|稍后补|稍后添加|稍后更新|TODO|TBD)", re.I)
FIELD_SOURCE = re.compile(r"(?:source|url|链接)\s*[:：]\s*(\S+)")

# 小红书成品规格（P0：标签与互动引导硬指标）
TAG_RE = re.compile(r"#[\u4e00-\u9fa5A-Za-z0-9_\-]+")
XHS_CTA_RE = re.compile(r"评论区|评论|留言|聊聊|互动|收藏|点赞|关注|告诉我|讨论|下方")

# 公众号参考来源（P0：禁止"链接待补"、至少 1 个可点击来源）
REF_HEADER_RE = re.compile(r"^#+\s*(参考来源|数据来源|来源|References)", re.M)

SCHEMA_ITEM = re.compile(r"（\s*source_type\s*[:：]\s*(真实数据|用户投喂|AI推断)\s*[|｜]\s*priority\s*[:：]\s*(核心|辅助)\s*）")

PLATFORM_DIRS = ["小红书", "公众号", "短视频"]


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def normalize(s):
    """去空白与标点差异，用于稳健子串匹配。"""
    return re.sub(r"[\s\*`#>「」“”\"'，。、：:；;！!？?（）()\[\]【】—\-…·]+", "", s)


def parse_frontmatter(text):
    """极简 frontmatter 解析（免 pyyaml）：返回 dict 或 None。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return None
    data = {}
    for line in m.group(1).splitlines():
        km = re.match(r"(\w+)\s*:\s*(.*)", line.strip())
        if km:
            data[km.group(1)] = km.group(2).strip()
    cm = data.get("consumed_materials", "")
    # 支持 M1/M3 与 A2/A4 两种编号体系（防止 A 系列假报关漏检）
    data["consumed_materials"] = re.findall(r"[MA]\d+", cm)
    return data


def parse_materials(text):
    """
    解析素材包。返回 (items, schema_complete)。
    items: [{id, text, source_type, priority, tokens}]
    优先按 schema 标注解析；无标注时降级为 legacy 模式（提取数字/Hook 条目）。
    """
    items = []
    lines = text.splitlines()
    auto_id = 0
    for i, ln in enumerate(lines):
        m = SCHEMA_ITEM.search(ln)
        if not m:
            continue
        body = SCHEMA_ITEM.sub("", ln).lstrip("-*0123456789.、 ").strip()
        # 显式编号优先（如 "M1｜…" / "M3: …"）；无显式编号的条目用 A 前缀自动编号，避免撞号
        explicit = re.search(r"\bM(\d+)\s*[｜|:：]", body)
        if explicit:
            item_id = f"M{explicit.group(1)}"
        else:
            auto_id += 1
            item_id = f"A{auto_id}"
        tokens = NUMBER_TOKEN.findall(body)
        url_m = FIELD_SOURCE.search(ln) or URL_RE.search(ln)
        if not url_m:
            # 素材包的 URL 常写在条目下一行的「来源：」里，向后看 2 行
            for look in lines[i + 1:i + 3]:
                look_url = URL_RE.search(look)
                if look_url:
                    url_m = look_url
                    break
        # 概念型素材（无"数字+单位"）兜底关键词：取标题段（｜后、：前），去掉通用后缀
        title_seg = re.split(r"[：:]", body)[0]
        title_seg = re.sub(r"^M\d+\s*[｜|:：]\s*", "", title_seg)
        title_seg = title_seg.strip().strip("*").strip()
        title_seg = re.sub(r"(概念|数据|研究|报告|事实|机制|实证|断崖|清单|概念卡)$", "", title_seg)
        kw = normalize(title_seg)
        items.append({
            "id": item_id, "text": body[:60],
            "source_type": m.group(1), "priority": m.group(2),
            "tokens": tokens, "norm": normalize(body), "kw": kw,
            "url": (url_m.group(1) if url_m and url_m.re.groups else (url_m.group(0) if url_m else None)),
            "placeholder": bool(PLACEHOLDER_SOURCE.search(ln)),
        })

    if items:
        return items, True

    # ---- legacy 模式：无 schema 标注的老素材包 ----
    in_hook = False
    mid = 0
    for ln in lines:
        if re.match(r"#+.*Hook", ln, re.I):
            in_hook = True
            continue
        if ln.startswith("#"):
            in_hook = False
        stripped = ln.strip().lstrip("-*0123456789.、 ").strip()
        if not stripped:
            continue
        if in_hook and len(stripped) >= 8:
            mid += 1
            items.append({"id": f"M{mid}", "text": stripped[:60],
                          "source_type": "legacy-hook", "priority": "核心",
                          "tokens": [], "norm": normalize(stripped[:12]), "kw": ""})
        else:
            toks = NUMBER_TOKEN.findall(stripped)
            if toks:
                mid += 1
                # legacy 包无 priority 信息，含具体数字的条目一律视同核心做衰减检查
                items.append({"id": f"M{mid}", "text": stripped[:60],
                              "source_type": "legacy-data", "priority": "核心",
                              "tokens": toks, "norm": normalize(stripped), "kw": ""})
    return items, False


def material_url_issues(items):
    """
    素材来源可溯源检查（P0）：
    - 真实数据 必须带可打开链接（http/https）；
    - 任何条目出现"链接待补/来源待补"占位即 FAIL。
    返回 [(code, message), ...]。
    """
    issues = []
    for it in items:
        if it["source_type"] == "真实数据" and not it.get("url"):
            issues.append((
                "C8-url-required",
                f"真实数据必须带可打开链接（source/url 字段）：{it['id']}「{it['text']}…」",
            ))
        if it.get("placeholder"):
            issues.append((
                "C8-url-placeholder",
                f"素材含『链接/来源待补』占位：{it['id']}「{it['text']}…」",
            ))
    return issues


def duplicate_paragraphs(text):
    """公众号整段重复检测：去 frontmatter 后按空行分段，返回重复段落（归一化后）。"""
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.S)
    seen = {}
    dups = []
    for para in re.split(r"\n{2,}", body):
        norm = re.sub(r"\s+", "", para)
        if len(norm) < 15:
            continue
        if norm in seen:
            if seen[norm] == 1:
                dups.append(norm[:40])
            seen[norm] += 1
        else:
            seen[norm] = 1
    return dups[:3]


def find_drafts(output_dir):
    drafts = {}
    for plat in PLATFORM_DIRS:
        for path in sorted(glob.glob(os.path.join(output_dir, plat, "*.md"))):
            drafts.setdefault(plat, []).append(path)
    return drafts


def platform_completeness(output_dir):
    """
    按 workflows/产出标准.md 核对平台目录完整性（P0）：
    - 小红书/公众号 必须存在且含文案.md；
    - 短视频 为选配：目录存在时必须有分镜脚本 md，缺失目录不判错。
    返回 [(level, code, message)]。
    """
    issues = []
    for plat, need_md in (("小红书", True), ("公众号", True)):
        d = os.path.join(output_dir, plat)
        if not os.path.isdir(d):
            issues.append(("FAIL", "C10-dir-missing", f"[{plat}] 目录缺失（产出标准要求必须交付）"))
            continue
        if need_md and not glob.glob(os.path.join(d, "*.md")):
            issues.append(("FAIL", "C10-dir-empty", f"[{plat}] 目录存在但没有文案.md"))
    vdir = os.path.join(output_dir, "短视频")
    if os.path.isdir(vdir) and not glob.glob(os.path.join(vdir, "*.md")):
        issues.append(("FAIL", "C10-dir-empty", "[短视频] 目录存在但没有分镜脚本 md"))
    if not os.path.exists(os.path.join(output_dir, "评分报告.md")):
        issues.append(("WARN", "C10-score-report", "缺少 评分报告.md（质检链会自动生成；strict 模式下视为 FAIL）"))
    return issues


def gzh_data_viz_issues(output_dir):
    """
    C11（数据可视化硬门）：公众号排版 HTML 必须包含 ≥2 个 data-viz 组件；
    且不得残留 [[IMG:...]] 正文图片占位符。
    """
    issues = []
    html_files = [
        p for p in glob.glob(os.path.join(output_dir, "公众号", "*.html"))
        if "_预览" not in os.path.basename(p) and "移动端预览" not in os.path.basename(p)
    ]
    for p in html_files:
        html = read_text(p)
        count = len(re.findall(r'data-viz\s*=\s*"([^"]+)"', html))
        if count < 2:
            issues.append((
                "FAIL", "C11-viz-count",
                f"[公众号] {os.path.basename(p)} 数据可视化组件 {count} 个（要求 ≥2：表格/条形/占比/KPI）",
            ))
        placeholders = re.findall(r"\[\[IMG:[^\]]+\]\]", html)
        if placeholders:
            issues.append((
                "FAIL", "C11-img-placeholder",
                f"[公众号] {os.path.basename(p)} 含未替换的正文图片占位符 {placeholders[:3]}",
            ))
    return issues


def xhs_data_viz_issues(output_dir):
    """
    C12（数据可视化硬门）：小红书 slides HTML 必须含条形/占比可视化标记。
    """
    issues = []
    for p in sorted(glob.glob(os.path.join(output_dir, "小红书", "rednote_*.html"))):
        html = read_text(p)
        if not re.search(r"h-bar-chart|bar-tower|data-viz", html):
            issues.append((
                "FAIL", "C12-viz-missing",
                f"[小红书] {os.path.basename(p)} 缺少条形/占比可视化标记"
                "（h-bar-chart / bar-tower / data-viz），关键数字对比必须可视化",
            ))
    return issues


def find_material_pack(output_dir, explicit):
    if explicit:
        return explicit if os.path.exists(explicit) else None
    job = os.path.basename(os.path.normpath(output_dir))
    date = job.split("_")[0]
    month = date[:7]
    # 优先精确匹配本 Job 的素材包（同日多 Job 时 glob[0] 会拿错包）
    exact = os.path.join("materials", month, f"{job}素材包.md")
    if os.path.exists(exact):
        return exact
    cands = sorted(glob.glob(os.path.join("materials", month, f"{date}_*素材包.md")))
    return cands[0] if cands else None


def main():
    ap = argparse.ArgumentParser(description="素材契约校验器")
    ap.add_argument("output_dir", help="产出目录 outputs/YYYY-MM-DD_主题名/")
    ap.add_argument("--materials", help="显式指定素材包路径")
    ap.add_argument("--strict", action="store_true", help="严格模式：WARN 也视为 FAIL")
    ap.add_argument("--json", action="store_true", help="输出 JSON 报告")
    ap.add_argument("--out", help="将 JSON 报告落盘到指定路径（供周报聚合，建议 outputs/<job_id>/validate_report.json）")
    args = ap.parse_args()

    results = []  # (level, code, message)

    def report(level, code, msg):
        results.append({"level": level, "code": code, "message": msg})

    # ---------- C0: 素材包定位 ----------
    pack_path = find_material_pack(args.output_dir, args.materials)
    items, schema_complete = [], False
    if not pack_path:
        report("WARN", "C0-no-pack", "未找到对应素材包，跳过素材契约检查（可用 --materials 显式指定）")
    else:
        items, schema_complete = parse_materials(read_text(pack_path))
        if schema_complete:
            report("PASS", "C0-pack", f"素材包 schema 完整：{pack_path}（{len(items)} 条标注素材）")
        else:
            report("WARN", "C0-legacy",
                   f"素材包无 schema 标注（legacy 模式降级检查）：{pack_path}。新素材包必须带 (source_type|priority) 标注")

    core = [it for it in items if it["priority"] == "核心"]
    if items and schema_complete:
        if 3 <= len(core) <= 5:
            report("PASS", "C1-core-count", f"核心素材数量 {len(core)} 条（要求 3-5）")
        else:
            report("FAIL", "C1-core-count", f"核心素材数量 {len(core)} 条，不符合 3-5 条要求")

    # ---------- C8: 素材来源可溯源（P0） ----------
    if items:
        for code, msg in material_url_issues(items):
            report("FAIL", code, msg)

    # ---------- C2: 成稿 frontmatter ----------
    drafts = find_drafts(args.output_dir)
    draft_meta = {}
    for plat, paths in drafts.items():
        for p in paths:
            text = read_text(p)
            fm = parse_frontmatter(text)
            draft_meta[p] = {"text": text, "norm": normalize(text), "fm": fm}
            if fm is None:
                report("WARN" if not args.strict else "FAIL", "C2-frontmatter",
                       f"[{plat}] {os.path.basename(p)} 缺少 frontmatter 契约（job_id/consumed_materials/hook_formula）")
            else:
                report("PASS", "C2-frontmatter", f"[{plat}] {os.path.basename(p)} frontmatter 完整")
                if plat in ("小红书", "公众号") and not (fm.get("hook_formula") or "").strip():
                    report("FAIL", "C2-hook-formula",
                           f"[{plat}] {os.path.basename(p)} 缺少 hook_formula（标题/开头公式编号，小红书/公众号必填）")

    # ---------- C3: 核心素材消费率（素材衰减检测） ----------
    if items:
        consumed_ids = set()
        all_norm = "".join(v["norm"] for v in draft_meta.values())
        for it in core:
            hit = False
            if it["tokens"]:
                hit = any(re.search(re.escape(t.replace(" ", "")), all_norm.replace(" ", "")) for t in it["tokens"])
            if not hit and it.get("kw") and len(it["kw"]) >= 2:
                hit = it["kw"] in all_norm
            if not hit and it["norm"]:
                hit = it["norm"] in all_norm
            if hit:
                consumed_ids.add(it["id"])
                report("PASS", "C3-consumed", f"核心素材 {it['id']}「{it['text']}…」已被引用")
            else:
                report("FAIL", "C3-decay",
                       f"素材衰减：核心素材 {it['id']}「{it['text']}…」未在任何成稿中被实质性引用")
        if core:
            rate = len(consumed_ids) / len(core)
            lvl = "PASS" if rate >= 1.0 else "FAIL"
            report(lvl, "C3-rate", f"核心素材引用率 {len(consumed_ids)}/{len(core)} = {rate:.0%}（要求 100%）")

    # ---------- C4: consumed_materials 报关核对 ----------
    for p, v in draft_meta.items():
        fm = v["fm"]
        if not fm:
            continue
        ids = fm["consumed_materials"]
        valid = {it["id"] for it in items}
        fake = [i for i in ids if i not in valid]
        if fake:
            report("FAIL", "C4-fake-id", f"{os.path.basename(p)} consumed_materials 含无效编号 {fake}（假报关嫌疑）")
        ai_infer = [i for i in ids if any(it["id"] == i and it["source_type"] == "AI推断" for it in items)]
        if ai_infer:
            report("WARN", "C4-ai-infer", f"{os.path.basename(p)} 引用了 AI推断 素材 {ai_infer}，禁止作为事实引用，仅可作观点启发")

    # ---------- C5: 数据密度 ----------
    for p, v in draft_meta.items():
        nums = NUMBER_TOKEN.findall(v["text"])
        plat = next(k for k in PLATFORM_DIRS if k in p)
        threshold = 2 if plat in ("小红书", "公众号") else 1
        lvl = "PASS" if len(nums) >= threshold else "FAIL"
        report(lvl, "C5-density",
               f"[{plat}] {os.path.basename(p)} 具体数字 {len(nums)} 处（要求 ≥{threshold}）：{nums[:6]}")

    # ---------- C6: AI 腔开头 ----------
    for p, v in draft_meta.items():
        body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", v["text"], flags=re.S)
        body = re.sub(r"^#+ .*$", "", body, flags=re.M).strip()[:150]
        for pat in BANNED_OPENINGS:
            if re.search(pat, body):
                report("FAIL", "C6-ai-opening",
                       f"{os.path.basename(p)} 命中禁用开头句式 /{pat}/：「{body[:40]}…」")
                break

    # ---------- C7: 油腻/违禁短语 ----------
    for p, v in draft_meta.items():
        hits = [g for g in GREASY_PHRASES if g in v["text"]]
        if hits:
            report("FAIL", "C7-greasy", f"{os.path.basename(p)} 含违禁短语：{hits}")

    # ---------- C9: 平台成品硬指标（P0） ----------
    for p, v in draft_meta.items():
        plat = next(k for k in PLATFORM_DIRS if k in p)
        if plat == "小红书":
            tags = TAG_RE.findall(v["text"])
            if len(tags) < 5:
                report("FAIL", "C9-xhs-tags",
                       f"[小红书] 搜索标签 {len(tags)} 个（要求 ≥5）：{tags[:6]}")
            if not XHS_CTA_RE.search(v["text"]):
                report("FAIL", "C9-xhs-cta",
                       "[小红书] 缺少互动引导（评论区/收藏/点赞/关注/聊聊等）")
        elif plat == "公众号":
            dups = duplicate_paragraphs(v["text"])
            if dups:
                report("FAIL", "C9-gzh-dup",
                       f"[公众号] 存在整段重复（{len(dups)} 段，如「{dups[0]}…」），需去重后重审")
            ref_present = bool(REF_HEADER_RE.search(v["text"]))
            if PLACEHOLDER_SOURCE.search(v["text"]):
                report("FAIL", "C9-gzh-ref-placeholder",
                       "[公众号] 参考来源含『链接/来源待补』占位，禁止交付")
            elif ref_present and not URL_RE.search(v["text"]):
                report("FAIL", "C9-gzh-ref-links",
                       "[公众号] 有参考来源区块但全文无任何可点击链接")
            elif not ref_present:
                lvl = "WARN" if not args.strict else "FAIL"
                report(lvl, "C9-gzh-ref-missing",
                       "[公众号] 缺少文末『参考来源』区块（产出标准要求）")

    # ---------- C10: 目录完整性（P0） ----------
    for lvl, code, msg in platform_completeness(args.output_dir):
        report(lvl, code, msg)

    # ---------- C11/C12: 数据可视化硬门 ----------
    for lvl, code, msg in gzh_data_viz_issues(args.output_dir):
        report(lvl, code, msg)
    for lvl, code, msg in xhs_data_viz_issues(args.output_dir):
        report(lvl, code, msg)

    # ---------- 汇总 ----------
    fails = [r for r in results if r["level"] == "FAIL"]
    warns = [r for r in results if r["level"] == "WARN"]

    if args.out:
        report_doc = {
            "output_dir": args.output_dir,
            "materials": pack_path,
            "validated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "verdict": "REJECTED" if fails else ("CONDITIONAL" if warns else "PASSED"),
            "fails": len(fails), "warns": len(warns), "results": results,
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report_doc, f, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps({"fails": len(fails), "warns": len(warns), "results": results}, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print("📜 素材契约校验报告")
        print("=" * 60)
        for r in results:
            icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[r["level"]]
            print(f"{icon} [{r['code']}] {r['message']}")
        print("-" * 60)
        verdict = "❌ REJECTED" if fails else ("⚠️ CONDITIONAL PASS" if warns else "✅ PASSED")
        print(f"结论：{verdict}（FAIL {len(fails)} / WARN {len(warns)}）")

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
