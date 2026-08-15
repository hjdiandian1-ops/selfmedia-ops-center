---
name: theme-design-skill
description: 为自媒体运营工作台（及同类原生 HTML/CSS 应用）设计、实现与切换皮肤主题。Use when 用户要求新增/修改皮肤、主题、配色、暗黑模式，或询问主题切换怎么做。工作流基于 CSS 自定义属性（design tokens）+ data-theme 属性 + localStorage 持久化，参考 Open Props / Radix Colors / DaisyUI / Catppuccin / Tokyo Night / theme.park 等开源方案。
---

# Theme Design Skill（主题皮肤设计）

## 原则

- 颜色只通过 CSS 变量（token）表达，组件内禁止散落原始 hex；新主题 = 新增一个 `[data-theme="..."]` token 覆盖块，不改组件代码。
- 默认主题保持 `:root`（蓝白）不变，任何新主题都不得影响默认体验。
- 深浅主题都要过 WCAG AA 对比度检查（正文 ≥4.5:1，大字号/图标 ≥3:1）。
- 先出方案（色板 + 影响面 + 风险）给用户批准，再动手实现。

## 工作流

### 1. 盘点现有 token

读 `webapp/static/style.css` 的 `:root`，当前 token 有：

`--primary / --primary-strong / --on-primary / --primary-container / --on-primary-container / --surface / --surface-dim / --on-surface / --on-surface-variant / --outline / --outline-variant / --error / --success / --radius-lg/md/sm / --shadow-1/2`

已知硬编码残留（新主题需一并 token 化或按主题覆盖）：

- `.brand-logo` 渐变（蓝 → 浅蓝）
- `.badge.success/.error/.hit` 背景
- `.toast.ok/.err` 背景
- `.x-zone`、`.step.current .dot`、`.chip:hover` 中的主题色
- `app.js` 中 `color:#3c4043` 的正文预览
- 图表/条形组件中的色值（若存在）

### 2. 选参考体系

按需求查阅 `references/theme-systems.md`，常见选型：

- 需要暗黑 + 多 flavor：Catppuccin / Tokyo Night
- 需要无障碍色阶：Radix Colors
- 需要主题切换机制：DaisyUI（`data-theme` + theme-change）
- 需要完整设计 token 库：Open Props / shadcn-ui
- 需要整套应用皮肤思路：theme.park

### 3. 定色板

把新主题写入 `references/palettes.json`（机器可读，唯一事实源），格式见文件内示例。每个主题至少覆盖：背景（surface/surface-dim）、正文（on-surface/on-surface-variant）、主色与容器色（primary 系列）、边框（outline 系列）、成功/错误、品牌渐变。

### 4. 对比度检查

```bash
python3 skills/theme-design-skill/scripts/theme_contrast_check.py --theme brand-red
python3 skills/theme-design-skill/scripts/theme_contrast_check.py --all
```

失败（正文 <4.5:1、按钮文字 <4.5:1）必须调色后重跑。

### 5. 实现

在 `webapp/static/style.css` 的 `:root` 后追加：

```css
:root[data-theme="brand-red"] {
  --primary: #dc2626;
  /* ... 其余 token 覆盖 ... */
}
```

切换与持久化（`app.js` + `index.html` head 内联，防止闪白）：

```html
<script>
  document.documentElement.dataset.theme =
    localStorage.getItem("selfmedia_theme") || "default";
</script>
```

```js
function cycleTheme() {
  const names = ["default", "brand-red", "midnight", "paper", "swiss"];
  const cur = document.documentElement.dataset.theme || "default";
  const next = names[(names.indexOf(cur) + 1) % names.length];
  document.documentElement.dataset.theme = next;
  localStorage.setItem("selfmedia_theme", next);
  toast("已切换主题：" + next);
}
```

侧边栏底部放「🌗 主题」按钮；暗黑主题下同时检查弹窗、表格、状态徽章、图表与 toast 的对比度。

### 6. 验收

- `theme_contrast_check.py --all` 全绿；
- 每个主题下截图走查 7 个视图 + 设置弹窗 + 成品预览，无遮挡、无“灰底黑字看不清”；
- 浏览器刷新后主题保持（localStorage）；
- 全量测试 `python3 -m pytest tests -q` 不受影响（CSS/HTML 改动）；
- 默认主题视觉与改动前一致。

## 资源

- `references/theme-systems.md`：GitHub 开源主题系统调研（选型依据、许可证、借鉴点）
- `references/palettes.json`：主题色板唯一事实源（含 WCAG 检查用关键配对）
- `scripts/theme_contrast_check.py`：对比度检查脚本（读 palettes.json）
