# GitHub 主题/皮肤系统调研（2026-08-15）

按“可借鉴度 × 许可证友好度”挑选，只学思路与结构，不复制代码。

| 项目 | 地址 | 许可证 | 核心思路 | 本项目的借鉴点 |
|---|---|---|---|---|
| Open Props | [argyleink/open-props](https://github.com/argyleink/open-props) | MIT | 全套 CSS 自定义属性设计 token（颜色/阴影/动效/字号/间距） | token 分层命名与“变量即规范”的写法；新增主题只需覆盖变量 |
| Radix Colors | [radix-ui/colors](https://github.com/radix-ui/colors) | MIT | 12 步无障碍色阶，每步都有明确用途（背景/悬停/边框/文字） | 主题色不从单一主色“深/浅”猜，而按语义步骤选值，保证对比度 |
| DaisyUI | [saadeghi/daisyui](https://github.com/saadeghi/daisyui) | MIT | `data-theme` 属性 + 主题包，官方推荐 `theme-change` 用 localStorage 持久化 | 主题切换机制：`data-theme` + localStorage + 提前注入防闪白 |
| Catppuccin | [catppuccin/catppuccin](https://github.com/catppuccin/catppuccin) | MIT | 4 个 flavor（Latte/Frappe/Macchiato/Mocha），26 色一套，跨工具统一 | 暗黑主题的“柔和粉彩”配色与多 flavor 组织方式 |
| Tokyo Night | [folke/tokyonight.nvim](https://github.com/folke/tokyonight.nvim) | Apache-2.0 | 深蓝夜底色 + 霓虹点缀，语义角色映射完整（bg/fg/accent） | 深色工作台配色：`#1a1b26` 底 + `#7aa2f7` 主色，专注但不刺眼 |
| theme.park | [themepark-dev/theme.park](https://github.com/themepark-dev/theme.park) | MIT | 为 50+ 自托管应用做皮肤包，CSS 变量注入 + 统一皮肤库 | “一套皮肤多个应用”的维护方式：皮肤 = 变量包，应用只消费变量 |
| shadcn/ui | [shadcn-ui/ui](https://github.com/shadcn-ui/ui) | MIT | CSS 变量 + OKLCH 色空间三层 token（全局/语义/组件） | 三层 token 思路与主题生成器（[shadcnthemes](https://github.com/subhadeeproy3902/shadcnthemes)）的实时预览流程 |

## 结论

本项目（原生 HTML/CSS 工作台）采用：

1. **token 层**：`style.css :root` 现有变量为唯一颜色入口；
2. **主题层**：`[data-theme="x"]` 覆盖块，新增皮肤不碰组件代码；
3. **切换层**：`data-theme` + localStorage，`index.html` head 内联脚本防闪白；
4. **验收层**：WCAG 对比度脚本 + 全页面截图走查。

深色主题参考 Catppuccin Mocha / Tokyo Night；浅色品牌主题参考 Radix Colors 语义色阶 + 本项目 cover-design-skill 的红白品牌规范。
