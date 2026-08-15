---
name: color-system-skill
description: 设计/校验 UI 主题配色体系：主色 + 协调色（近似、互补、分裂互补、三角）、色阶与语义 token、WCAG 对比度。Use when 需要新增主题色板、生成协调色、校准/评审配色规范，或把品牌色扩展成完整设计色板。
---

# 色彩设计规范

## 核心流程

1. 定主色：读取品牌/用户指定色，转 HSV 记录色相。
2. 选配色方案，生成 `palette-1..4`（主色 + 3 协调色），见 `references/color-theory.md`。
3. 为每个颜色补语义 token：主色 / 容器色 / on-color / 边框 / 背景 / 成功 / 错误。
4. 深浅模式分别过 WCAG：正文 ≥4.5:1，大字号/图标 ≥3:1。
5. 写入 `skills/theme-design-skill/references/palettes.json`（唯一事实源）与 `webapp/static/style.css` 的 `[data-theme]` 块。

## 生成协调色

```bash
python3 skills/color-system-skill/scripts/harmonize_palette.py \
  --primary "#1a73e8" --scheme triadic
```

支持 `analogous / split / triadic / complementary`，输出 4 色 + 色相差。
校验现有主题色板是否和谐：

```bash
python3 skills/color-system-skill/scripts/harmonize_palette.py \
  --check skills/theme-design-skill/references/palettes.json
```

## 校验对比度

```bash
python3 skills/theme-design-skill/scripts/theme_contrast_check.py --all
```

失败必须调色后重跑，禁止把 FAIL 主题上线。

## 参考文档（按需读取）

- `references/color-theory.md`：色相环与五种配色方案，含 HSV 计算。
- `references/system-survey.md`：Radix Colors / Open Color / Catppuccin / Primer / Material / shadcn 的要点与链接。
- `references/token-hierarchy.md`：primitive → semantic → component 三级 token、深浅模式与无障碍规则。

## 红线

- 颜色只走 CSS token，组件内禁止散落原始 hex。
- 数据可视化至少 4 色且色相差尽量拉大；正文色永远用语义 token。
- 新主题不得修改默认主题 `:root` 的既有值。
