#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
极简快速质检器（纯 Python 标准库 · 0 依赖 · 毫秒级执行）
=========================================================
支持：
  1. 单个 Markdown / HTML / TXT 文件快速质检
  2. 任意文件夹批量递归质检
  3. 终端直接传入纯文本字符串质检

质检项目：
  - 去 AI 味 22 条量化规则（句式壳、机械过渡、助手腔、对称收束等）
  - 平台合规与广告法极限词（最佳/第一/保本/医疗功效/涉政涉黄涉赌等）

用法：
    python3 scripts/quick_check.py 文章草稿.md
    python3 scripts/quick_check.py outputs/2026-08-16_xxx/
    python3 scripts/quick_check.py --text "值得注意的是，在这个日新月异的时代..."
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import ai_flavor_check
import compliance_check


def check_text_or_path(target_path=None, text_content=None):
    if text_content:
        # 内存字符串检测
        texts = {"直接输入文本": text_content}
        comp_report = compliance_check.run_on_texts(texts) if hasattr(compliance_check, "run_on_texts") else {}
        ai_report = ai_flavor_check.run_on_texts(texts) if hasattr(ai_flavor_check, "run_on_texts") else {}
    else:
        comp_report = compliance_check.run(target_path)
        ai_report = ai_flavor_check.run(target_path)

    print("=" * 64)
    print("🚀 自媒体运营工厂 · 快速质检报告（去AI味 + 内容合规）")
    print("=" * 64)

    # 1. 去 AI 味报告
    ai_s = ai_report.get("summary", {})
    ai_verdict = ai_report.get("verdict", "PASSED")
    ai_icon = {"PASSED": "✅", "WARN": "⚠️", "REJECTED": "🛑"}.get(ai_verdict, "ℹ️")
    print(f"\n【1. 去 AI 味 22 条规则检测】{ai_icon} {ai_verdict}")
    print(f"   命中项：高风险 {ai_s.get('high', 0)} 处 ｜ 中风险 {ai_s.get('medium', 0)} 处 ｜ 总计 {ai_s.get('total_hits', 0)} 处")
    for h in ai_report.get("hits", [])[:6]:
        sev_icon = {"high": "🛑", "medium": "⚠️"}.get(h.get("severity"), "ℹ️")
        print(f"   {sev_icon} [{h.get('rule')}] {h.get('source', '')} ×{h.get('count', 1)}")
        for ex in h.get("examples", [])[:1]:
            print(f"      👉 示例：{ex}")

    # 2. 合规报告
    comp_s = comp_report.get("summary", {})
    comp_verdict = comp_report.get("verdict", "PASSED")
    comp_icon = {"PASSED": "✅", "WARN": "⚠️", "REJECTED": "🛑"}.get(comp_verdict, "ℹ️")
    print(f"\n【2. 平台合规与敏感词检测】{comp_icon} {comp_verdict}")
    print(f"   命中项：高风险 {comp_s.get('high', 0)} 处 ｜ 中风险 {comp_s.get('medium', 0)} 处 ｜ 建议 {comp_s.get('warn', 0)} 处")
    for c in comp_report.get("checks", [])[:6]:
        sev_icon = {"high": "🛑", "medium": "⚠️", "warn": "💡"}.get(c.get("severity"), "ℹ️")
        print(f"   {sev_icon} {c.get('message', '')}（敏感词：{c.get('keyword', '')}）")
        if c.get("evidence"):
            print(f"      👉 原文：{c.get('evidence')[:60]}")

    print("\n" + "-" * 64)
    overall = "REJECTED" if (ai_verdict == "REJECTED" or comp_verdict == "REJECTED") else (
        "WARN" if (ai_verdict == "WARN" or comp_verdict == "WARN") else "PASSED"
    )
    overall_icon = {"PASSED": "🎉 完美过检，建议直接发布！", "WARN": "⚠️ 存在部分优化建议，建议人工复核后发布", "REJECTED": "🛑 存在高风险违禁/重度AI味，必须修改后发布"}[overall]
    print(f"【最终结论】：{overall_icon}")
    print("-" * 64)
    return 0 if overall in ("PASSED", "WARN") else 1


def main():
    ap = argparse.ArgumentParser(description="自媒体极简快速质检器（0 依赖）")
    ap.add_argument("target", nargs="?", default="", help="待检文件或目录路径")
    ap.add_argument("--text", help="直接输入待检文本字符串")
    args = ap.parse_args()

    if not args.target and not args.text:
        ap.print_help()
        print("\n💡 提示：你可以直接传入单个文件测试，例如：python3 scripts/quick_check.py README.md")
        return 1

    return check_text_or_path(target_path=args.target, text_content=args.text)


if __name__ == "__main__":
    raise SystemExit(main())
