#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据可视化组件生成器（公众号 + 小红书共用）
===========================================
生成带内联样式、可被质检脚本机器校验（data-viz 标记）的 HTML 数据组件：
  table  数据表格
  bar    水平条形图（对比）
  ratio  占比条
  kpi    KPI 对比卡
  complex 复杂图（PNG 模式）：环形占比图卡，用本地无头浏览器渲染 750px PNG

用法：
    python3 scripts/generate_data_viz.py --spec data.json --out component.html
    python3 scripts/generate_data_viz.py --spec complex.json --png --out chart.png

spec JSON 结构：
    {"type": "bar", "title": "标题", "primary": "#DC2626",
     "items": [{"label": "命中", "value": 0.02, "display": "0.02 元"}],
     "source": "数据来源"}
    complex 额外字段：{"center": "50倍", "center_label": "价差",
                       "segments": [{"label": "A", "value": 60, "color": "#DC2626"}]}
"""
import argparse
import json
import os
import pathlib

DEFAULT_PRIMARY = "#DC2626"


def _src_block(source):
    if not source:
        return ""
    return (
        '<div style="padding:12px 18px 14px;font-size:12px;color:#9CA3AF;'
        'border-top:1px dashed #F3E2E2;margin-top:12px;">数据来源：'
        f"{source}</div>"
    )


def render_table(spec):
    """
    表格组件（微信安全版）：纯 div/span + inline-block，禁止 <table>——
    微信编辑器会把 <table> 拆成文本框导致排版错乱（2026-08-08 数据飞轮沉淀）。
    """
    headers = spec.get("headers", ["项目", "数据"])
    cols = ["width:34%", "width:33%", "width:30%"]
    head_html = "".join(
        f'<span style="display:inline-block;box-sizing:border-box;{cols[i]};'
        f'color:#9CA3AF;font-size:12px;padding:0 6px;">{h}</span>'
        for i, h in enumerate(headers)
    )
    rows_html = ""
    for it in spec.get("items", []):
        vals = [it.get("label", ""), it.get("col2", ""), it.get("display", it.get("value", ""))]
        cells = []
        for i, v in enumerate(vals):
            style = f"display:inline-block;box-sizing:border-box;{cols[i]};font-size:14px;padding:0 6px;"
            if i == 0:
                style += "color:#6B7280;"
            elif i == len(vals) - 1:
                style += f"color:{spec.get('primary', DEFAULT_PRIMARY)};font-weight:800;text-align:right;"
            else:
                style += "color:#1C1917;"
            cells.append(f'<span style="{style}">{v}</span>')
        rows_html += (
            f'<div style="padding:10px 4px;border-top:1px solid #F5F5F5;line-height:1.6;">'
            f'{"".join(cells)}</div>'
        )
    return (
        '<section data-viz="table" '
        'style="margin:24px 0;background:#fff;border:1px solid #F3E2E2;border-radius:12px;overflow:hidden;">'
        f'<div style="padding:14px 18px;background:#FEF2F2;font-size:15px;font-weight:800;color:#1C1917;">'
        f'{spec.get("title", "")}</div>'
        f'<div style="padding:12px 14px;">'
        f'<div style="background:#FAFAFA;border-radius:8px;padding:9px 0;">{head_html}</div>'
        f'{rows_html}</div>'
        f'{_src_block(spec.get("source"))}</section>'
    )


def render_bar(spec):
    items = spec.get("items", [])
    max_val = max((it.get("value", 0) for it in items), default=1) or 1
    rows = []
    for it in items:
        pct = max(2, round(it.get("value", 0) / max_val * 100))
        rows.append(
            '<div style="margin-bottom:14px;">'
            '<div style="margin-bottom:6px;">'
            f'<span style="display:inline-block;box-sizing:border-box;width:64%;'
            f'color:#6B7280;font-size:13px;">{it["label"]}</span>'
            f'<span style="display:inline-block;box-sizing:border-box;width:34%;text-align:right;'
            f'font-weight:800;color:{spec.get("primary", DEFAULT_PRIMARY)};font-size:13px;">'
            f'{it.get("display", it.get("value"))}</span></div>'
            '<div style="background:#F5F5F5;border-radius:999px;height:8px;overflow:hidden;">'
            f'<div style="width:{pct}%;height:8px;background:'
            f'{spec.get("primary", DEFAULT_PRIMARY)};border-radius:999px;"></div></div>'
            "</div>"
        )
    return (
        '<section data-viz="bar" '
        'style="margin:24px 0;background:#fff;border:1px solid #F3E2E2;border-radius:12px;padding:18px;">'
        f'<div style="font-size:15px;font-weight:800;color:#1C1917;margin-bottom:14px;">'
        f'{spec.get("title", "")}</div>{"".join(rows)}'
        f'{_src_block(spec.get("source"))}</section>'
    )


def render_ratio(spec):
    item = spec.get("item", {})
    pct = max(0.0, min(100.0, round(float(item.get("value", 0)), 1)))
    pct_txt = f"{pct:g}"
    return (
        '<section data-viz="ratio" '
        'style="margin:24px 0;background:#fff;border:1px solid #F3E2E2;border-radius:12px;padding:18px;">'
        f'<div style="font-size:15px;font-weight:800;color:#1C1917;margin-bottom:14px;">'
        f'{spec.get("title", "")}</div>'
        '<div style="background:#F5F5F5;border-radius:999px;height:14px;overflow:hidden;">'
        f'<div style="width:{pct_txt}%;height:14px;background:'
        f'{spec.get("primary", DEFAULT_PRIMARY)};border-radius:999px;"></div></div>'
        '<div style="margin-top:8px;">'
        f'<span style="display:inline-block;box-sizing:border-box;width:70%;'
        f'font-size:13px;color:#6B7280;">{item.get("label", "")}</span>'
        f'<span style="display:inline-block;box-sizing:border-box;width:28%;text-align:right;'
        f'font-weight:800;color:{spec.get("primary", DEFAULT_PRIMARY)};font-size:13px;">'
        f'{item.get("display", item.get("value"))}（{pct_txt}%）</span></div>'
        f'{_src_block(spec.get("source"))}</section>'
    )


def render_kpi(spec):
    items = spec.get("items", [])
    tds = []
    for it in items:
        delta = it.get("delta", "")
        delta_style = "color:#059669;"
        if str(delta).startswith("-"):
            delta_style = "color:#DC2626;"
        tds.append(
            f'<div style="display:inline-block;box-sizing:border-box;width:32%;'
            f'padding:8px 2px;text-align:center;vertical-align:top;">'
            f'<div style="font-size:24px;font-weight:900;color:'
            f'{spec.get("primary", DEFAULT_PRIMARY)};">{it.get("display", it.get("value"))}</div>'
            f'<div style="font-size:12px;color:#6B7280;margin-top:4px;">{it["label"]}</div>'
            f'<div style="font-size:12px;{delta_style}font-weight:700;margin-top:2px;">{delta}</div>'
            "</div>"
        )
    return (
        '<section data-viz="kpi" '
        'style="margin:24px 0;background:#fff;border:1px solid #F3E2E2;border-radius:12px;padding:18px;">'
        f'<div style="font-size:15px;font-weight:800;color:#1C1917;margin-bottom:8px;">'
        f'{spec.get("title", "")}</div>'
        f'<div style="margin:10px 0 4px;">{"".join(tds)}</div>'
        f'{_src_block(spec.get("source"))}</section>'
    )


def render_component(spec):
    typ = spec.get("type", "table")
    if typ == "table":
        return render_table(spec)
    if typ == "bar":
        return render_bar(spec)
    if typ == "ratio":
        return render_ratio(spec)
    if typ == "kpi":
        return render_kpi(spec)
    raise ValueError(f"未知组件类型：{typ}（支持 table/bar/ratio/kpi/complex）")


def render_complex_png(spec, out_path):
    """环形占比图卡 → 750px 宽 PNG（本地无头浏览器渲染）。"""
    segments = spec.get("segments", [])
    total = sum(s.get("value", 0) for s in segments) or 1
    stops = []
    acc = 0.0
    for s in segments:
        start = acc / total * 360
        acc += s.get("value", 0)
        end = acc / total * 360
        stops.append(f"{s.get('color', DEFAULT_PRIMARY)} {start:.1f}deg {end:.1f}deg")
    legend = "".join(
        '<div style="display:flex;align-items:center;margin-bottom:12px;">'
        f'<span style="display:inline-block;width:16px;height:16px;border-radius:4px;'
        f'background:{s.get("color", DEFAULT_PRIMARY)};margin-right:10px;"></span>'
        f'<span style="font-size:16px;color:#374151;">{s.get("label", "")}</span>'
        f'<span style="margin-left:auto;font-size:16px;font-weight:800;color:#111827;">'
        f'{round(s.get("value", 0) / total * 100, 1)}%</span></div>'
        for s in segments
    )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head><body style="margin:0;">
<div style="width:750px;padding:40px;background:#fff;font-family:-apple-system,'PingFang SC',sans-serif;box-sizing:border-box;">
  <div style="font-size:28px;font-weight:900;color:#111827;">{spec.get("title", "")}</div>
  <div style="margin:28px 0;display:flex;align-items:center;">
    <div style="width:260px;height:260px;border-radius:50%;background:conic-gradient({', '.join(stops)});position:relative;">
      <div style="position:absolute;inset:46px;background:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-direction:column;">
        <div style="font-size:42px;font-weight:900;color:#111827;">{spec.get("center", "")}</div>
        <div style="font-size:16px;color:#9CA3AF;">{spec.get("center_label", "")}</div>
      </div>
    </div>
    <div style="margin-left:40px;flex:1;">{legend}</div>
  </div>
  <div style="font-size:15px;color:#9CA3AF;">数据来源：{spec.get("source", "")}</div>
</div>
</body></html>"""
    tmp_html = pathlib.Path(out_path).with_suffix(".png.html")
    tmp_html.write_text(html, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 750, "height": 500},
                                    device_scale_factor=2)
            page.goto(tmp_html.resolve().as_uri())
            page.wait_for_timeout(600)
            page.screenshot(path=out_path, full_page=True)
            browser.close()
    finally:
        if tmp_html.exists():
            tmp_html.unlink()
    print(f"🖼 复杂图 PNG 已生成：{out_path}")


def main():
    ap = argparse.ArgumentParser(description="数据可视化组件生成器")
    ap.add_argument("--spec", required=True, help="JSON spec 文件")
    ap.add_argument("--out", required=True, help="输出文件（html 或 png）")
    ap.add_argument("--png", action="store_true", help="复杂图 PNG 模式")
    args = ap.parse_args()

    with open(args.spec, "r", encoding="utf-8") as f:
        spec = json.load(f)
    if args.png or spec.get("type") == "complex":
        render_complex_png(spec, args.out)
        return 0
    html = render_component(spec)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📊 数据组件已生成：{args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
