# 三级 Token 与无障碍规则

## 三级结构

1. **primitive（原始）**：`--blue-500`、`--orange-500` 等纯色阶。
2. **semantic（语义）**：`--primary`、`--surface`、`--error`、`--success`、`--palette-1..4`。
3. **component（组件）**：`--btn-bg`、`--card-bg`；组件只引用 semantic，不直接引用 primitive。

本项目落地：CSS 直接维护 semantic；palettes.json 为唯一事实源；主题切换只覆盖 semantic。

## 语义角色最小集

| 角色 | 用途 |
| --- | --- |
| primary / on-primary | 主按钮、主操作 |
| primary-container / on-primary-container | 选中态、浅底强调 |
| surface / on-surface / on-surface-variant | 页面与卡片层级、正文 |
| outline / outline-variant | 边框分隔 |
| error / success | 状态 |
| palette-1..4 | 图表、平台、多序列 |

## WCAG 阈值

- 正文 ≥4.5:1；大字号（≥18pt 或 14pt 粗体）与图标 ≥3:1。
- 对比度按实际“文字色 vs 所在背景色”计算，不是对主色算一次。
- 暗色主题正文用高亮前景（如 #e9f6ff）而不是纯白，减少刺眼。

## 深浅模式

- light：surface 最亮、surface-dim 略灰；文字最深。
- dark：surface 暗、surface-dim 更暗；文字用 85-95% 亮度，次要文字 65-75%。
- 同主题的 aurora/阴影随模式重定义，禁止一套阴影通吃。
