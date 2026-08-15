# GitHub 流行色彩体系调研

| 体系 | 仓库/文档 | 核心方法 | 借鉴点 |
| --- | --- | --- | --- |
| Radix Colors | https://github.com/radix-ui/colors | 每色族 1-12 阶语义刻度，浅深两套，支持 alpha 阶 | 语义刻度而非随意色值；accent 统一驱动组件 |
| Open Color | https://github.com/yeun/open-color | 12 色族 × 9-10 阶，专为 UI 文字/背景/边框优化 | 固定阶数、明度步进一致 |
| Catppuccin | https://github.com/catppuccin/catppuccin | 26 色跨 4 种明度风味（latte/frappe/macchiato/mocha） | 一套色相关系复制到多种明度 |
| Primer（GitHub） | https://primer.github.io/design/foundations/color/ | light/dark 双模式 + 多主题，对比度策略内建 | 每个模式独立验证 WCAG，防色弱 |
| Material Design 3 | https://m3.material.io/styles/color | primary/secondary/error/surface 角色 + on-color 对比 | 语义角色表：容器、on-color、hover、focus |
| shadcn/ui | https://github.com/shadcn-ui/ui | OKLCH 色彩空间 + primitive→semantic→component 三级 token | 感知均匀的 OKLCH，广色域 P3 |
| 配色生成器 | https://github.com/alfaaarex/huekit | 互补/近似/三角/自定义方案生成 | 配色方案算法可复现 |

## 提炼后的通用规则

1. 色板分三层：原始色阶（primitive）→ 语义 token（semantic）→ 组件引用（component）。
2. 每个语义色必须有 on-color（如 primary ↔ on-primary），并过 WCAG。
3. 深浅模式不是把颜色变暗，而是同时调背景与前景的明度层级。
4. 流行体系都固定“色族数量 × 阶数”，不随机造色。
5. 对比度检查应内建到 CI/测试，而不是靠人眼。
