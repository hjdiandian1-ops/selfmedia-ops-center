# 📝 更新日志 (Changelog)

本项目所有重要更新与功能演进均记录于此。

遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 格式与 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/) 规范。

## [v2.0.0] - 2026-08-22

### 🚀 Agent Skills 模块化重构与跨 IDE 技能套件升级
- **5 大标准 Agent Skills 技能包**：
  - `selfmedia-director`：自媒体总编·总控调度与四重质检门禁
  - `selfmedia-radar`：爆款雷达·微信公众号真实低粉爆款抓取、小红书/B站搜索、5平台音视频转录
  - `selfmedia-production`：工业化创作·素材事实清单萃取与三平台爆款正文生成
  - `selfmedia-visual`：高颜值排版·Playwright 2x Retina 3:4 组图无损渲染与架构流程图
  - `selfmedia-video`：短视频成片·HTML转1080x1920 MP4 B-roll逐帧渲染、-18dB动态侧链混音成片
- **纯 Python 3.9+ 统一核心底层**：封装在 `src/selfmedia/`，零 node_modules 膨胀，跨平台一键安装。
- **统一终端 CLI（`python -m selfmedia`）**：支持 radar/produce/check/install 完整命令体系。
- **跨 AI IDE 一键安装**：支持一键软链挂载到 `~/.cursor/skills`、`~/.claude/skills`、`~/.codex/skills`。
- **25 项全自动化质检测试**：覆盖全部 5 大技能领域与端到端 E2E 闭环（100% 通过）。
- **详尽升级文档**：新增 [docs/UPGRADE_GUIDE_V2.md](docs/UPGRADE_GUIDE_V2.md)。

---

## [v1.1.0] - 2026-08-21

### 🕐 内置定时调度器（无人值守）
- **新增 `webapp/scheduler.py` + `routers/scheduler.py`**：选题抓取、爆款采集拆解、周经验聚合、48h 数据回收四类任务各自独立定时，配置存 `data/scheduler.json`；
- **设置页「定时任务」面板**：逐任务启用开关、添加/删除时间点、立即运行一次；应用打开期间按点触发（默认关闭，生产/采纳仍由用户手动拍板）。

### 🧠 生产引擎升级（Codex 主链路 + 真实素材）
- **Codex 接入生产主链路**：`run_production.py` 统一走 `_generate()`，按「设置 → AI 引擎」的模式（auto / API 直连 / Codex CLI / WorkBuddy）自动选择引擎，Codex 不可用时回退 API；
- **素材阶段真实正文抓取**：新增 `scripts/fetch_source_content.py`（纯标准库），生产前抓取采纳链接与热点雷达相关条目的原文正文做 grounding，不再只靠模型记忆编造；
- **AI 引擎设置增强**：引擎模式选择、当前模型显示、累计 token 用量统计（`data/llm_usage.json`）、一键清空 LLM 配置。

### 🐛 修复
- **选题反馈模型修复**：`topic_feedback.py` 的 `extract_topic_features()` 原先调用参数不匹配被静默吞掉、导致权重校准恒无效，现已重写（质量/IP 维度随主题真实变化）；
- **生产质量修复**：删除会编造数字的素材兜底模板；修复文风指南被截断成末尾 1500 字的问题；Stage1 注入真实热点雷达 + 原文 grounding；
- **爆款拆解证据标注**：报告显著区分「真实分析（有原文）/ 推断拆解（仅标题）」，并提示补原文重拆；
- **device_fingerprint 跨平台修复**：`os.uname().nodename` 在 macOS 报错，改用 `platform.node()`。

### ⚙️ 交互与体验
- **生产队列按时间倒序**，超过 1 周的已完成任务折叠进「已归档」；
- **生产任务支持删除**（`DELETE /api/production/{job_id}`），选题页与流水线均可删；
- **数据飞轮/周经验包去向可见**：生成后明确提示写入路径与升级的 SOP 文件。

### 📦 发布与开源
- **发布白名单补全**：`release/build_public_repo.py` 补齐 `webapp/routers/*`、`core.py`、`scheduler.py`、`topic_feedback.py`、`fetch_source_content.py`、`.github/`、CHANGELOG、截图等，修复发布快照断链；
- **`.gitignore` 加固**：真实数据/成品/凭据（data、jobs、outputs、materials、nas 等）整体不入 git，本地保留、公网干净；
- **授权目录去个人化**：`~/.xiaowuliao-*` → `~/.selfmedia-*`，并支持 `SELFMEDIA_SKILLS_DIR` / `SELFMEDIA_LICENSE_DIR` 环境变量；
- **token 批量发码**：`token_mint.py` 新增 `--batch`，对接面包多自动发货；
- **提交前检查**：新增 `.pre-commit-config.yaml`（每次 commit 自动跑 `pytest tests/ -q`）；
- **界面截图**：Playwright 自动截图脚本 `scripts/capture_screenshots.py` + 8 张真实界面截图。

---

## [v1.0.0] - 2026-08-19

### 🚀 架构重构与工作台
- **FastAPI 模块化 Router**：将单体后端完整拆解为 8 大功能 Router (`overview`, `topics`, `viral`, `flywheel`, `production`, `outputs`, `stats`, `settings`) 与公共核心库 `core.py`；
- **8 套高审美主题系统**：支持 LV 奢华棋盘格、香奈儿蔚蓝、爱马仕橙、日系奶油、赛博霓虹等 8 套主题无缝切换与无级毛玻璃质感调节；
- **移动端与窄屏响应式适配**：完成桌面、平板 (768-1023px)、手机 (<768px) 三级断点适配，移动端支持底部导航栏与表格卡片化降级；
- **首启向导 (Onboarding Wizard)**：为新用户提供 4 步快速上手向导（欢迎与模型测试 → 热点雷达试玩 → 文风预设体验 → 配置清单确认）。

### ⚙️ 生产流水线与 Agent 协同
- **4 阶段解耦生产流水线**：将原单次长 prompt 调用彻底解耦为 4 步独立阶段（素材收集 → 平台文案初稿 → 视觉组件排版 → 四重质检）；
- **8 态状态机闭环**：`topic` → `materials` → `draft` → `visual` → `review` → `archive` → `publish` → `recycle`，实现中间状态与产物完整落盘；
- **质检自愈与人工升级**：质检打回自动携带错误报告触发针对性自愈重写，连续打回 2 次自动挂起并转交人工复核；
- **9 大 Agent SOP 自动升级**：结合数据飞轮自动将沉淀经验反哺写入 Agent 提示词。

### 🎯 智能选题与数据反馈回路
- **多源热点雷达**：集成今日热榜 AI 专题、推楼 1 号（X 中文区）、hex2077 AI 日报与 RSS 订阅源；
- **双池评分机制**：根据时效、热度、表达、搜索、持久、独特与跨源印证，精准拆分「日选题池」与「周选题池」；
- **选题评分动态校准 (Feedback Loop)**：构建「采纳 → 生产 → 发布 → 回填 → 校准」闭环，通过皮尔逊相关性自适应调整评分权重（±30% 保护上限）。

### 🛡️ 四重质检门禁与趋势可视化
- **四重质检门禁**：素材契约校验（核心素材 100% 引用率）、Harsh Critic 80分红线、去 AI 味 22 条禁令检测、三平台广告合规审核；
- **SVG 趋势走势图**：纯原生 Vanilla JS + SVG 渲染近 30 天质检通过率与 Harsh 评分走势图，支持 hover Tooltip 与里程碑徽章展示。

### 🧪 自动化测试体系
- **206 项自动化测试**：覆盖单元测试、API 集成测试、安全合规扫描与「选题到归档」E2E 端到端全链路自动化测试，测试通过率 100%。

---
