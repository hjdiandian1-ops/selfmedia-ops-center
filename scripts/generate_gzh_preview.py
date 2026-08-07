#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公众号移动端预览 HTML 生成器
============================
把 gzh-design 输出的主排版 HTML 包进“工具栏 + 一键复制到公众号”的预览外壳，
并可选生成 390px 移动端截图（mobile_check.png）。

用法：
    python3 scripts/generate_gzh_preview.py \
        --input outputs/<job>/公众号/gzh_<主题>_排版_<主题色>.html \
        [--output outputs/<job>/公众号/gzh_<主题>_排版_<主题色>_预览.html] \
        [--screenshot outputs/<job>/公众号/mobile_check.png]
"""
import argparse
import os
import pathlib

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body{{margin:0;background:#eef0f2;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;-webkit-text-size-adjust:100%;}}
  .gzh-toolbar{{position:fixed;top:0;left:0;right:0;height:54px;background:#ffffff;box-shadow:0 1px 10px rgba(0,0,0,.08);display:flex;align-items:center;justify-content:space-between;padding:0 16px;z-index:99;}}
  .gzh-hint{{font-size:13px;color:#6b7280;line-height:1.4;}}
  .gzh-hint b{{color:#111827;}}
  .gzh-copy{{background:#059669;color:#fff;border:0;border-radius:9px;padding:10px 20px;font-size:14px;font-weight:700;cursor:pointer;box-shadow:0 3px 10px rgba(5,150,105,.28);white-space:nowrap;transition:transform .08s,background .15s;}}
  .gzh-copy:hover{{background:#047857;}}
  .gzh-copy:active{{transform:translateY(1px);}}
  .gzh-toast{{position:fixed;top:66px;left:50%;transform:translateX(-50%);background:#111827;color:#fff;padding:11px 20px;border-radius:10px;font-size:14px;font-weight:600;opacity:0;pointer-events:none;transition:opacity .25s;z-index:100;box-shadow:0 6px 20px rgba(0,0,0,.25);max-width:88vw;text-align:center;}}
  .gzh-toast.show{{opacity:1;}}
  .gzh-stage{{max-width:700px;margin:78px auto 64px;padding:0 8px;}}
  @media(max-width:520px){{.gzh-hint{{max-width:150px;}}}}
</style>
</head>
<body>
<div class="gzh-toolbar">
  <span class="gzh-hint">👇 下方是排版效果 · 点右侧 <b>复制</b> 直接粘到公众号</span>
  <button class="gzh-copy" id="gzhCopyBtn" onclick="gzhCopy()">📋 复制到公众号</button>
</div>
<div class="gzh-toast" id="gzhToast"></div>
<div class="gzh-stage">
  <div id="gzh-content">
{content}
  </div>
</div>
<script>
  function gzhShowToast(msg){{
    var t=document.getElementById('gzhToast');
    t.textContent=msg;t.classList.add('show');
    clearTimeout(t._timer);
    t._timer=setTimeout(function(){{t.classList.remove('show');}},2800);
  }}
  function gzhCopy(){{
    var el=document.getElementById('gzh-content');
    var range=document.createRange();
    range.selectNodeContents(el);
    var sel=window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    var ok=false;
    try{{ok=document.execCommand('copy');}}catch(e){{ok=false;}}
    sel.removeAllRanges();
    var btn=document.getElementById('gzhCopyBtn');
    if(ok){{
      gzhShowToast('✅ 已复制！去公众号编辑器按 Ctrl/⌘+V 粘贴即可');
      var old=btn.textContent;btn.textContent='✅ 已复制';
      setTimeout(function(){{btn.textContent=old;}},2200);
    }}else{{
      gzhShowToast('⚠ 自动复制失败，请手动全选(Ctrl/⌘+A)再复制(Ctrl/⌘+C)');
    }}
  }}
</script>
</body>
</html>
"""


def generate(main_html, out_path):
    with open(main_html, "r", encoding="utf-8") as f:
        content = f.read()
    stem = os.path.basename(main_html).rsplit(".", 1)[0]
    html = TEMPLATE.format(title=f"{stem} · 公众号排版预览", content=content)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📄 预览 HTML 已生成：{out_path}")
    return out_path


def screenshot(out_path, png_path):
    from playwright.sync_api import sync_playwright
    uri = pathlib.Path(out_path).resolve().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844},
                                device_scale_factor=2)
        page.goto(uri)
        page.wait_for_timeout(1200)
        page.screenshot(path=png_path, full_page=True)
        browser.close()
    print(f"📱 移动端截图已生成：{png_path}")


def main():
    ap = argparse.ArgumentParser(description="公众号预览 HTML 生成器")
    ap.add_argument("--input", required=True, help="主排版 HTML")
    ap.add_argument("--output", default="", help="预览 HTML 输出路径")
    ap.add_argument("--screenshot", default="", help="移动端截图 PNG 输出路径")
    args = ap.parse_args()

    if not args.output:
        stem = os.path.basename(args.input).rsplit(".", 1)[0]
        args.output = os.path.join(os.path.dirname(args.input), f"{stem}_预览.html")
    generate(args.input, args.output)
    if args.screenshot:
        screenshot(args.output, args.screenshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
