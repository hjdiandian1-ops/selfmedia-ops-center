#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
README 截图占位图生成器 (Screenshot Placeholder Generator)
==========================================================
在正式截图录制前，为 docs/screenshots/ 生成「窗口化占位图」，避免 GitHub
README 出现 8 张破图。纯标准库实现（zlib + struct + 5x7 位图字体），无第三方依赖。

用法：
    python3 scripts/generate_screenshot_placeholders.py          # 生成全部占位图
    python3 scripts/generate_screenshot_placeholders.py --dry-run

生成后请按 docs/screenshots/README.md 的清单替换为真实截图（本脚本产物仅占位）。
"""
import argparse
import os
import struct
import zlib

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_DIR = os.path.join(ROOT, "docs", "screenshots")

# ---------- 5x7 位图字体（大写 + 数字 + 少量符号） ----------
FONT = {
    "A": [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    "C": [" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "],
    "D": ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    "G": [" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ### "],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"],
    "J": ["  ###", "   # ", "   # ", "   # ", "#  # ", "#  # ", " ##  "],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "S": [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"],
    "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    "0": [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"],
    "2": [" ### ", "#   #", "    #", "  ## ", " #   ", "#    ", "#####"],
    "3": ["#####", "   # ", "  #  ", " ### ", "    #", "#   #", " ### "],
    "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    "5": ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    "6": [" ### ", "#    ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "],
    " ": ["     ", "     ", "     ", "     ", "     ", "     ", "     "],
    "-": ["     ", "     ", "     ", "#####", "     ", "     ", "     "],
    ".": ["     ", "     ", "     ", "     ", "     ", " ##  ", " ##  "],
    ":": ["     ", " ##  ", " ##  ", "     ", " ##  ", " ##  ", "     "],
    "/": ["    #", "    #", "   # ", "  #  ", " #   ", "#    ", "#    "],
    "_": ["     ", "     ", "     ", "     ", "     ", "     ", "#####"],
}


def _text_w(text, scale):
    return (6 * len(text) - 1) * scale if text else 0


def _draw_text(buf, w, h, x, y, text, scale, rgb):
    for i, ch in enumerate(text):
        glyph = FONT.get(ch.upper(), FONT[" "])
        for r, row in enumerate(glyph):
            for c, col in enumerate(row):
                if col != "#":
                    continue
                px = x + i * 6 * scale + c * scale
                py = y + r * scale
                for dy in range(scale):
                    for dx in range(scale):
                        yy, xx = py + dy, px + dx
                        if 0 <= xx < w and 0 <= yy < h:
                            off = (yy * w + xx) * 3
                            buf[off:off + 3] = rgb


def _write_png(path, w, h, buf):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter: None
        raw += buf[y * w * 3:(y + 1) * w * 3]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8bit RGB
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)


SCREENSHOTS = [
    ("00-onboarding-demo.png", 1280, 720, "SELF-MEDIA OPS CENTER", "3 MIN ONBOARDING DEMO"),
    ("01-dashboard-overview.png", 1920, 1080, "01 DASHBOARD OVERVIEW", "DATA OVERVIEW + DIAGNOSIS"),
    ("02-topics-radar.png", 1920, 1080, "02 TOPICS RADAR", "MULTI-SOURCE HOT RADAR + DUAL POOL"),
    ("03-viral-breakdown.png", 1920, 1080, "03 VIRAL BREAKDOWN", "TOP10 TRACKING + AI BREAKDOWN"),
    ("04-production-pipeline.png", 1920, 1080, "04 PRODUCTION PIPELINE", "4-STAGE PIPELINE + STATE MACHINE"),
    ("05-outputs-preview.png", 1920, 1080, "05 OUTPUTS PREVIEW", "XHS / WECHAT / VIDEO PREVIEW"),
    ("06-qa-trends.png", 1920, 1080, "06 QA TRENDS", "4-GATE QA + SVG TREND CHARTS"),
    ("07-theme-showcase.png", 1920, 720, "07 THEME SHOWCASE", "8 HIGH-AESTHETIC THEMES"),
]


def generate(out_dir=OUT_DIR):
    for fname, w, h, title, subtitle in SCREENSHOTS:
        buf = bytearray(w * h * 3)
        # 顶部浏览器栏 + 纵向渐变背景
        bar_h = max(28, h // 28)
        c_top = (15, 23, 42)
        c_bot = (30, 41, 59)
        for y in range(h):
            t = y / max(1, h - 1)
            r = int(c_top[0] + (c_bot[0] - c_top[0]) * t)
            g = int(c_top[1] + (c_bot[1] - c_top[1]) * t)
            b = int(c_top[2] + (c_bot[2] - c_top[2]) * t)
            if y < bar_h:
                r, g, b = 8, 13, 26
            for x in range(w):
                off = (y * w + x) * 3
                buf[off:off + 3] = bytes((r, g, b))
        # 三个红绿灯圆点
        for i, dot in enumerate(((239, 68, 68), (250, 204, 21), (34, 197, 94))):
            cx = 18 + i * 26
            cy = bar_h // 2
            for dy in range(-6, 7):
                for dx in range(-6, 7):
                    if dx * dx + dy * dy <= 36:
                        xx, yy = cx + dx, cy + dy
                        if 0 <= xx < w and 0 <= yy < h:
                            off = (yy * w + xx) * 3
                            buf[off:off + 3] = bytes(dot)
        # 中央标题 + 副标题 + 底部说明
        scale = max(6, w // 52)
        _draw_text(buf, w, h, (w - _text_w(title, scale)) // 2, h // 2 - int(h * 0.06), title, scale, bytes((226, 232, 240)))
        s2 = max(2, w // 130)
        _draw_text(buf, w, h, (w - _text_w(subtitle, s2)) // 2, h // 2 + int(h * 0.08), subtitle, s2, bytes((148, 163, 184)))
        s3 = max(2, w // 160)
        footer = "PLACEHOLDER - REPLACE WITH REAL SCREENSHOT"
        _draw_text(buf, w, h, (w - _text_w(footer, s3)) // 2, h - int(h * 0.06), footer, s3, bytes((100, 116, 139)))
        _write_png(os.path.join(out_dir, fname), w, h, buf)
        print(f"✅ {fname} ({w}x{h})")
    return [s[0] for s in SCREENSHOTS]


def main():
    ap = argparse.ArgumentParser(description="README 截图占位图生成器")
    ap.add_argument("--out", default=OUT_DIR, help="输出目录（默认 docs/screenshots/）")
    args = ap.parse_args()
    files = generate(args.out)
    print(f"\n共生成 {len(files)} 张占位图，请按 docs/screenshots/README.md 清单替换为真实截图。")


if __name__ == "__main__":
    main()
