#!/usr/bin/env python3
"""
封面规格检查：尺寸/比例/底部留白/正文宽幅硬门。

用法:
    python3 check_cover_specs.py <图片路径或目录> [--type xhs|gzh-cover21|gzh-square|gzh-inline|auto]

退出码: 0 = PASS, 1 = FAIL。
"""

import argparse
import os
import sys

from PIL import Image


XHS_SIZE = (1080, 1440)
BOTTOM_WHITESPACE_LIMIT = 120  # 小红书 1080x1440 画布底部留白上限 (px)
MIN_INLINE_RATIO = 1.6


def load_rgb(path):
    im = Image.open(path)
    if im.mode != "RGB":
        im = im.convert("RGB")
    return im


def classify_type(path):
    name = os.path.basename(path).lower()
    if "cover" in name and ("square" in name or "1x1" in name or "1-1" in name):
        return "gzh-square"
    if "cover" in name and ("wide" in name or "21x9" in name or "21-9" in name):
        return "gzh-cover21"
    if "inline" in name or (name.startswith("gzh_") and "cover" not in name):
        return "gzh-inline"
    if name.startswith("xhs-") or "rednote" in name or "_xhs_" in name:
        return "xhs"
    return "auto"


def bottom_whitespace(im, tolerance=14):
    """自底向上统计接近背景色的空白带高度（px）。背景色取底部 3 行中位像素。"""
    width, height = im.size
    px = im.load()
    rows = min(3, height)
    bg = [0, 0, 0]
    for channel in range(3):
        vals = sorted(
            px[x, height - 1 - r][channel]
            for r in range(rows)
            for x in range(0, width, 4)
        )
        bg[channel] = vals[len(vals) // 2]

    band = 0
    for y in range(height - 1, -1, -1):
        row_is_bg = True
        for x in range(0, width, 2):
            p = px[x, y]
            if any(abs(p[c] - bg[c]) > tolerance for c in range(3)):
                row_is_bg = False
                break
        if row_is_bg:
            band += 1
        else:
            break
    return band, tuple(bg)


def check_file(path, expected_type):
    issues = []
    warns = []
    try:
        im = load_rgb(path)
    except Exception as exc:
        print(f"[FAIL] {path}: 无法读取图片 ({exc})")
        return False

    width, height = im.size
    ratio = width / height if height else 0
    kind = expected_type if expected_type != "auto" else classify_type(path)

    if kind == "xhs":
        if (width, height) != XHS_SIZE:
            issues.append(f"小红书封面必须精确 1080x1440，实际 {width}x{height}")
        band, _ = bottom_whitespace(im)
        if band > BOTTOM_WHITESPACE_LIMIT:
            issues.append(f"底部留白 {band}px > 上限 {BOTTOM_WHITESPACE_LIMIT}px")
        elif band > BOTTOM_WHITESPACE_LIMIT * 0.6:
            warns.append(f"底部留白 {band}px 接近上限，建议压缩")
        print(f"[INFO] xhs 底部留白: {band}px")
    elif kind == "gzh-cover21":
        if abs(ratio - 21 / 9) > 0.08:
            issues.append(f"公众号 21:9 主封面宽高比应为 ≈2.33，实际 {ratio:.3f}")
    elif kind == "gzh-square":
        if abs(ratio - 1.0) > 0.02:
            issues.append(f"公众号 1:1 方封面宽高比应为 1.0，实际 {ratio:.3f}")
    elif kind == "gzh-inline":
        if ratio < MIN_INLINE_RATIO:
            issues.append(
                f"公众号正文插图宽高比必须 ≥{MIN_INLINE_RATIO}:1，实际 {ratio:.3f}"
            )
    else:
        if expected_type == "auto":
            if ratio < MIN_INLINE_RATIO:
                warns.append(
                    f"无法按文件名判定类型，宽高比 {ratio:.3f} < {MIN_INLINE_RATIO}，"
                    "请用 --type 显式指定"
                )

    for warn in warns:
        print(f"[WARN] {path}: {warn}")
    if issues:
        for issue in issues:
            print(f"[FAIL] {path}: {issue}")
        return False
    print(f"[PASS] {path} ({kind}, {width}x{height}, ratio={ratio:.3f})")
    return True


def main():
    parser = argparse.ArgumentParser(description="封面规格检查")
    parser.add_argument("path", help="图片文件或目录")
    parser.add_argument(
        "--type",
        choices=["xhs", "gzh-cover21", "gzh-square", "gzh-inline", "auto"],
        default="auto",
        help="目标类型；auto 按文件名推断，推断不出时走通用检查",
    )
    args = parser.parse_args()

    path = args.path
    if os.path.isdir(path):
        files = sorted(
            os.path.join(path, f)
            for f in os.listdir(path)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        )
        if not files:
            print(f"[FAIL] 目录 {path} 内没有图片文件")
            sys.exit(1)
    elif os.path.isfile(path):
        files = [path]
    else:
        print(f"[FAIL] 路径不存在: {path}")
        sys.exit(1)

    results = [check_file(f, args.type) for f in files]
    if all(results):
        print(f"\n✅ {len(files)} 张图全部 PASS")
        sys.exit(0)
    print(f"\n❌ {results.count(False)}/{len(files)} 张图 FAIL")
    sys.exit(1)


if __name__ == "__main__":
    main()
