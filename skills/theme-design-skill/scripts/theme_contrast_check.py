#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主题对比度检查：读 palettes.json，输出每个主题关键配对的 WCAG 对比度。
用法：
    python3 theme_contrast_check.py --theme brand-red
    python3 theme_contrast_check.py --all
退出码：任一配对 < 4.5:1（正文）返回 1；<3:1 也返回 1。
"""
import argparse
import json
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PALETTES = os.path.join(ROOT, "references", "palettes.json")


def rel_lum(hex_color):
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"非法颜色: {hex_color}")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = []
    for c in rgb:
        lin.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(fg, bg):
    l1, l2 = rel_lum(fg), rel_lum(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def check_theme(theme, pairs):
    tokens = theme["tokens"]
    results = []
    for pair in pairs:
        fg_key, bg_key = pair[0], pair[1]
        threshold = float(pair[2]) if len(pair) > 2 else 4.5
        fg, bg = tokens.get(fg_key), tokens.get(bg_key)
        if not fg or not bg:
            results.append((fg_key, bg_key, None, "缺少 token"))
            continue
        ratio = contrast(fg, bg)
        results.append((fg_key, bg_key, round(ratio, 2), "PASS" if ratio >= threshold else "FAIL"))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", default="")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    data = json.load(open(PALETTES, encoding="utf-8"))
    themes = data["themes"]
    pairs = data["pairs"]
    if args.theme:
        themes = [t for t in themes if t["id"] == args.theme]
    if not themes:
        print(f"未找到主题: {args.theme}")
        sys.exit(2)

    failed = False
    for t in themes:
        print(f"\n🎨 {t['name']}（{t['id']}）")
        for fg, bg, ratio, status in check_theme(t, pairs):
            line = f"  {fg} / {bg}: {ratio} → {status}"
            print(line)
            threshold = next((float(p[2]) for p in pairs if p[0] == fg and p[1] == bg), 4.5)
            if ratio is None or ratio < threshold:
                failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
