#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""协调色生成与校验工具。

用法：
    python3 harmonize_palette.py --primary "#1a73e8" --scheme triadic
    python3 harmonize_palette.py --check ../../theme-design-skill/references/palettes.json
"""
import argparse
import colorsys
import json
import sys


def hex_to_hsv(h):
    h = h.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"非法颜色: {h}")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)


def hsv_to_hex(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def shift(h, s, v, dh, ds=0.0, dv=0.0):
    return hsv_to_hex((h + dh / 360.0) % 1.0, s + ds, v + dv)


SCHEMES = {
    "analogous": [0, 35, -35, 70],
    "split": [0, 150, -150, 35],
    "triadic": [0, 120, -120, 0],
    "complementary": [0, 180, 40, -40],
}


def build(primary, scheme):
    if scheme not in SCHEMES:
        raise ValueError(f"未知方案: {scheme}，支持 {list(SCHEMES)}")
    h, s, v = hex_to_hsv(primary)
    deltas = SCHEMES[scheme]
    colors = [shift(h, s, v, d) for d in deltas]
    # 第 4 个同族深阶（deltas=0 时给出深色变体，避免与主色重复）
    if deltas[3] == 0:
        colors[3] = hsv_to_hex(h, s, v * 0.72)
    return {
        "primary": primary,
        "scheme": scheme,
        "palette-1": colors[0],
        "palette-2": colors[1],
        "palette-3": colors[2],
        "palette-4": colors[3],
        "hue-deltas": deltas,
    }


def hue_of(hex_color):
    return hex_to_hsv(hex_color)[0] * 360.0


def check_palettes(path):
    data = json.load(open(path, encoding="utf-8"))
    out = []
    for t in data["themes"]:
        if not t.get("implemented", False):
            continue
        toks = t["tokens"]
        keys = [f"palette-{i}" for i in range(1, 5)]
        if not all(k in toks for k in keys):
            out.append({"theme": t["id"], "error": "缺少 palette-1..4"})
            continue
        chromatic = []
        for k in keys:
            h, s, _v = hex_to_hsv(toks[k])
            if s >= 0.05:  # 近中性色（黑/白/灰）色相无意义，不参与色相差
                chromatic.append(h * 360.0)
        if not chromatic:
            out.append({"theme": t["id"], "hues": [], "min-gap": None, "note": "全中性色板"})
            continue
        hs = chromatic
        # 最小相邻色相差（环形距离）
        sorted_hs = sorted(hs)
        gaps = []
        for a, b in zip(sorted_hs, sorted_hs[1:]):
            d = (b - a) % 360
            gaps.append(min(d, 360 - d))
        d = (sorted_hs[0] - sorted_hs[-1]) % 360
        gaps.append(min(d, 360 - d))
        out.append({
            "theme": t["id"],
            "hues": [round(x, 1) for x in hs],
            "min-gap": round(min(gaps), 1),
            "note": "" if min(gaps) >= 40 else "存在近色对（品牌同族可接受，图表需靠明度区分）",
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--primary", default="")
    ap.add_argument("--scheme", default="triadic", choices=list(SCHEMES))
    ap.add_argument("--check", default="")
    args = ap.parse_args()
    if args.check:
        for row in check_palettes(args.check):
            print(json.dumps(row, ensure_ascii=False))
        return
    if not args.primary:
        ap.print_help()
        sys.exit(2)
    print(json.dumps(build(args.primary, args.scheme), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
