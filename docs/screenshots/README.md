# 📸 工作台截图与 GIF 录制规范 (Screenshots Guide)

本目录用于存放 GitHub README 与文档站展示的高清界面截图与演示动图。

## 规范清单与推荐尺寸

| 文件名 | 对应功能模块 | 推荐尺寸 | 截取建议 |
| :--- | :--- | :---: | :--- |
| `00-onboarding-demo.png` | 3 分钟首启向导与全自动生产演示 | 1280×720 (16:9) | 建议录制 10~15 秒 GIF（占位图为高清 PNG）：从侧边栏打开向导 → 测试 LLM → 查看推荐选题 → 采纳 |
| `01-dashboard-overview.png` | 数据中台与薄弱点诊断 | 1920×1080 | 包含 KPI 卡片、折线图与下方智能诊断建议（建议深色主题或 LV 奢华） |
| `02-topics-radar.png` | 多源热点雷达与双池推荐 | 1920×1080 | 展开日选题/周选题表格，带出时效/热度/质量明细与采纳按钮 |
| `03-viral-breakdown.png` | 爆款跟踪与 AI 拆解报告 | 1920×1080 | 弹窗展示 AI 拆解报告（含前3秒钩子、情绪共鸣、结构拆解） |
| `04-production-pipeline.png` | 流水线 4 阶段解耦与状态机 | 1920×1080 | 展示 8 态状态机进度条 + 实时运行日志 + 9 大 Agent 分工卡片 |
| `05-outputs-preview.png` | 成品库三平台排版预览 | 1920×1080 | 展示小红书 9:16 卡片轮播 或 公众号排版渲染效果 |
| `06-qa-trends.png` | 四重质检门禁与 SVG 趋势图 | 1920×1080 | 展示质检通过率走势折线图 + Harsh Critic 走势 + 里程碑勋章 |
| `07-theme-showcase.png` | 8 套高审美主题展示 | 1920×720 | 8 套主题配色与质感档位对比拼接图 |

## 截取技巧提示
- 推荐使用 Chrome DevTools `Cmd+Shift+P` → `Capture full size screenshot` 或 `Capture node screenshot`；
- 建议开启 2x Retina 缩放，图片保存前建议用 TinyPNG 或 `pngquant` 压缩，控制单张图片在 500KB 以内；
- GIF 推荐使用 [LiceCap](https://www.cockos.com/licecap/) 或 [ScreenToGif](https://www.screentogif.com/)，控制在 5MB 以内。
