---
name: selfmedia-visual
description: 自媒体高颜值视觉排版与出图｜用于小红书 62+ 套 3:4 HTML 组图渲染、公众号富文本排版、逻辑架构图生成及封面规范质检。
dependency:
  python:
    - playwright>=1.30.0
    - jinja2>=3.0.0
license: MIT
---

# 🎨 自媒体高颜值视觉排版与出图 (selfmedia-visual)

支持通过纯 HTML/CSS 结合 Playwright 渲染 2x Retina 无损超清图文组图与架构图。

---

## 🎯 核心能力

1. **小红书 3:4 组图无损渲染**：基于现代化设计规范，支持暗夜极客（dark-pro）、日系奶油（minimalist-cream）、赛博霓虹（cyber-neon）、奢华焦糖（lux-caramel）等风格。
2. **逻辑架构图生成**：自动生成步骤卡片流、对比矩阵、指标走势等现代信息图。
3. **封面规范检测**：自检大标题字数、视觉焦点与遮挡安全区。

---

## 🛠️ CLI 命令行用法

```bash
# 渲染小红书 3:4 组图
python3 -m selfmedia.visual.render --deck deck.json --theme dark-pro --out ./outputs/images

# 生成流程架构图 HTML 与图片
python3 -m selfmedia.visual.diagram --steps steps.json --out ./outputs/diagram.png
```
