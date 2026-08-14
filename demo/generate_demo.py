#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 demo 样例文章并跑一次去 AI 味检查（供公开仓库演示）。"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_DIR = os.path.join(ROOT, "demo", "样例文章")

SAMPLE = """---
title: demo
---

这是一篇用于演示质检能力的样例文章。文章里会刻意保留几处典型 AI 腔，
方便你观察去 AI 味检查的输出效果。

首先，我们要理解问题的背景；其次，我们需要分析核心原因；最后，给出结论。
本质上，这是一个流程问题。值得注意的是，这种情况并不少见。
这不是技术问题，而是习惯问题；不是工具问题，而是方法问题；不是速度问题，而是方向问题。
由此可见，规范化的检查很有必要。
"""


def main():
    os.makedirs(DEMO_DIR, exist_ok=True)
    with open(os.path.join(DEMO_DIR, "样例文章.md"), "w", encoding="utf-8") as f:
        f.write(SAMPLE)
    script = os.path.join(ROOT, "scripts", "ai_flavor_check.py")
    subprocess.run(
        [sys.executable, script, DEMO_DIR, "--out", os.path.join(ROOT, "demo", "ai_flavor_report.json")],
        cwd=ROOT, check=True,
    )
    print("✅ demo 已生成：demo/样例文章/ + demo/ai_flavor_report.json")


if __name__ == "__main__":
    raise SystemExit(main())
