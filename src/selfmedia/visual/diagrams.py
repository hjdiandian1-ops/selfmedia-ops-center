# -*- coding: utf-8 -*-
"""
Logic & Architecture Diagram Generator (逻辑架构与流程图解生成器)
============================================================
生成结构清晰、色彩现代的 HTML/SVG 逻辑架构图、对比矩阵图与步骤图。
"""

from __future__ import annotations

from typing import Any, Dict, List


def generate_pipeline_diagram_html(
    steps: List[Dict[str, str]],
    title: str = "自媒体工业化生产全流程 SOP",
    theme_accent: str = "#38bdf8",
) -> str:
    """生成漂亮的步骤流程图 HTML"""
    steps_html = []
    for idx, s in enumerate(steps, 1):
        step_title = s.get("title", f"步骤 {idx}")
        step_desc = s.get("desc", "")
        icon = s.get("icon", "⚡")
        steps_html.append(f"""
        <div class="step-card">
          <div class="step-header">
            <span class="step-badge">STEP 0{idx}</span>
            <span class="step-icon">{icon}</span>
          </div>
          <h3 class="step-title">{step_title}</h3>
          <p class="step-desc">{step_desc}</p>
        </div>
        """)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    background: #0f172a;
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
    padding: 60px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }}
  .title {{
    font-size: 40px;
    font-weight: 800;
    margin-bottom: 50px;
    color: #fff;
  }}
  .steps-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 24px;
    width: 100%;
    max-width: 1100px;
  }}
  .step-card {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .step-badge {{
    background: {theme_accent};
    color: #0f172a;
    font-size: 13px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 6px;
  }}
  .step-icon {{
    font-size: 24px;
  }}
  .step-title {{
    font-size: 20px;
    font-weight: 700;
  }}
  .step-desc {{
    font-size: 14px;
    color: #94a3b8;
    line-height: 1.5;
  }}
</style>
</head>
<body>
  <h1 class="title">{title}</h1>
  <div class="steps-grid">
    {''.join(steps_html)}
  </div>
</body>
</html>"""
    return html
