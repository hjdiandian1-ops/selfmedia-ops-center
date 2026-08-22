# 自媒体运营工厂 v2.0 · Agent Skills 升级与实战全景指南

> **一句话总结**：从 v1.0 单一本地 Web 工作台，全面重构升级为**纯 Python 原生、模块化 Agent Skills 技能套件与统一终端 CLI**。
> 深度吸收 SpaceZephyr/creator-buddy 的底层公域感知与音视频物理合成能力，并与我们自研的「四重质检门禁」和「工业化流水线」强强联合，完美适配 **Cursor / Claude Code / Codex / Antigravity / OpenClaw** 等主流 AI 运行时。

---

## 📑 目录

1. [新旧版本架构与能力全景对比](#一-新旧版本架构与能力全景对比)
2. [环境准备与一键安装指引](#二-环境准备与一键安装指引)
3. [Cursor / Claude Code / Codex 自然语言提示词范式](#三-cursor--claude-code--codex-自然语言提示词范式)
4. [统一终端 CLI 命令行实战手册](#四-统一终端-cli-命令行实战手册)
5. [5 大 Agent Skills 模块详解](#五-5-大-agent-skills-模块详解)
6. [回滚策略与常见问题排查 FAQ](#六-回滚策略与常见问题排查-faq)

---

## 一、 新旧版本架构与能力全景对比

| 对比维度 | v1.0 本地 Web 工作台 | 🚀 v2.0 Agent Skills 技能套件 (当前版本) |
|---|---|---|
| **产品形态** | 依赖浏览器打开 `127.0.0.1:8787` 的独立 Web 界面 | **纯 Agent Skills + 统一终端 CLI**，无缝嵌入任何 AI IDE 运行时（Cursor / Claude / Codex） |
| **爆款情报探测** | 主要抓取全网热搜词（微博/知乎/B站公域榜单） | **微信公众号真实低粉爆款抓取**（低粉高赞、10w+、原创飙升榜）+ **跨平台垂类搜索** |
| **音视频素材输入** | 需人工下载音视频并整理文字 | **跨平台一键转录**：支持 YouTube、小宇宙播客、B站、抖音、小红书链接，直接输出带时间戳 Markdown 逐字稿与 SRT 字幕 |
| **质检与门禁体系** | Prompt 级提示或部分打分 | **四重机器可算门禁**：素材事实契约校验 + 22条去AI味硬性过滤 + 广告法合规 + Harsh Critic 80分挑剔读者红线 |
| **视觉排版与出图** | 基础截图与模板卡片 | **Playwright 2x Retina 超清无损渲染**：小红书 3:4 组图（暗夜极客、日系奶油、赛博霓虹、奢华焦糖）+ 逻辑流程架构图生成 |
| **短视频生产深度** | 产物为《分镜脚本台本》（纯文本） | **物理成片 MP4 交付**：HTML ➔ 1080x1920 MP4 B-roll 逐帧渲染 + **-18dB 动态侧链避让混音** + 成片装配 |
| **底层技术栈** | 混合脚本与独立 Web 服务 | **纯 Python 3.9+ 原生收敛**，零 node_modules 膨胀，跨平台一键运行 |

---

## 二、 环境准备与一键安装指引

### 2.1 依赖安装（一次配置）

在项目根目录下执行：

```bash
# 安装核心依赖（包含 Playwright、yt-dlp、imageio-ffmpeg、jinja2）
python3 -m pip install -r requirements.txt
```

### 2.2 一键将 Skills 挂载到 AI 运行时

只需执行一行命令，系统会自动将 `skills/` 下的 5 大技能包软链到对应 IDE 的全局技能库：

```bash
# 一键安装到 Cursor / Claude Code / Codex 全局目录
PYTHONPATH=src python3 -m selfmedia install --target all
```

*已支持的挂载路径：*
- **Cursor**：`~/.cursor/skills/`
- **Claude Code**：`~/.claude/skills/`
- **Codex**：`~/.codex/skills/`
- **通用 Agent 协议**：`~/.agents/skills/`

---

## 三、 Cursor / Claude Code / Codex 自然语言提示词范式

安装后，在 AI IDE 聊天窗口中直接使用自然语言对话，Agent 会自动识别意图并路由调用对应技能：

### 🎯 场景 1：精准探测垂直赛道公众号爆款
```text
用户 ❯ 帮我查一下最近公众号关于【AI编程】有哪些低粉高阅读的爆款文章？

助手 ❯ 📡 正在调用 selfmedia-radar 探测公众号爆款...
       已找到 5 篇黑马低粉爆款：
       1. 【低粉爆款】时代变化得太快了（佳哥博客，阅读 10w+，点赞 1596）
       2. 【低粉爆款】早安！伏天吃葡萄 生津补钾（阅读 6w+，点赞 467）
       ...
       分析结论：当前受众更关注真实落地避坑细节与量化提效案例。
```

### 🎯 场景 2：外部音视频链接一键转录与拆解
```text
用户 ❯ 把这个 B站/小宇宙 链接提取一下逐字稿，并按素材契约拆出核心事实清单：
       https://www.bilibili.com/video/BV1xx411c7mD

助手 ❯ 🎬 正在调用 selfmedia-radar 提取音频并转录...
       ✅ 已生成带时间戳逐字稿：outputs/transcripts/xxx_transcript.md
       ✅ 正在生成《素材事实清单》，通过 Gate 1 素材契约校验！
```

### 🎯 场景 3：小红书高赞图文改写与四重门禁质检
```text
用户 ❯ 基于上面的事实清单，为小红书写一篇高赞图文笔记，要求严格执行去AI味和 80分读者评审。

助手 ❯ ✍️ 正在调用 selfmedia-production 生成小红书图文...
       🛡️ 触发 selfmedia-director 四重质检：
         - Gate 1 素材事实契约：100 分 ✅
         - Gate 2 去AI味人味得分：100 分（无任何公文套话）✅
         - Gate 3 广告法敏感词：0 处违规 ✅
         - Gate 4 Harsh Critic 读者评审：92 分（远超 80 分红线）✅
       📝 文案已交付...
```

### 🎯 场景 4：小红书 3:4 组图无损渲染与视频成片
```text
用户 ❯ 为刚才的小红书文案渲染一套暗夜极客风格的 3:4 组图，并把短视频分镜渲染出 1080x1920 的 B-roll 视频片段。

助手 ❯ 🎨 正在调用 selfmedia-visual 渲染 2x Retina 超清组图：
         - slide_01.png (1080x1440 2x Retina 无损)
         - slide_02.png (1080x1440 2x Retina 无损)
       🎬 正在调用 selfmedia-video 逐帧生成 MP4 B-roll 并执行侧链避让混音：
         - final_complete.mp4 (1080x1920 竖屏成片)
```

---

## 四、 统一终端 CLI 命令行实战手册

除了自然语言交互，你也可以在终端像使用 `git` 一样精准执行批处理任务：

```bash
# 查看统一 CLI 帮助文档
PYTHONPATH=src python3 -m selfmedia --help
```

### 1. 爆款情报与转录（`selfmedia radar`）
```bash
# 探测公众号指定赛道低粉爆款
PYTHONPATH=src python3 -m selfmedia radar gzh "AI编程" --limit 10

# 跨平台社媒聚合搜索（小红书 / B站 / 抖音）
PYTHONPATH=src python3 -m selfmedia radar search "独立开发"

# 一键转录任意链接为 Markdown + SRT 字幕
PYTHONPATH=src python3 -m selfmedia radar transcribe "https://www.bilibili.com/video/BV1xx..." --out ./outputs/transcripts
```

### 2. 工业化内容生产（`selfmedia produce`）
```bash
# 生成小红书爆款图文正文（自动过 4 重门禁）
PYTHONPATH=src python3 -m selfmedia produce xhs --topic "Cursor全自动开发工作流"

# 生成短视频 120s 黄金分镜台本
PYTHONPATH=src python3 -m selfmedia produce video --topic "独立开发者如何月入过万"
```

### 3. 四重质检门禁审核（`selfmedia check`）
```bash
# 针对任意本地 Markdown 文本执行全套质检
PYTHONPATH=src python3 -m selfmedia check ./outputs/我的草稿.md
```

---

## 五、 5 大 Agent Skills 模块详解

```text
skills/
├── selfmedia-director/        # 🎯 总指挥官：调度全流程 SOP，把控四重门禁与飞轮反哺
├── selfmedia-radar/           # 📡 情报雷达：微信公众号低粉爆款、小红书/B站搜索、链接转录
├── selfmedia-production/      # ✍️ 工业生产：素材事实清单萃取、小红书/公众号/短视频爆款改写
├── selfmedia-visual/          # 🎨 视觉排版：Playwright 2x Retina 3:4 组图无损渲染、架构图
└── selfmedia-video/           # 🎬 视频引擎：HTML转MP4 B-roll逐帧渲染、-18dB动态侧链混音成片
```

---

## 六、 回滚策略与常见问题排查 FAQ

### Q1：如果我想一秒回滚到 v1.0 版本怎么办？
我们在升级前已将 v1.0 全量状态推送到 GitHub 远程仓库做永久备份。如需回滚，在终端执行：
```bash
# 检出并恢复到 v1.0 安全备份分支
git checkout backup-v1.0-before-skills-upgrade
```

### Q2：音视频转录时，如何配置高精度 ASR 语音模型？
- **推荐方案（极速且免费）**：在系统环境变量或 `.env` 中配置 `GROQ_API_KEY="gsk_..."`，系统会自动调用云端 Whisper Large V3（10分钟音频仅需 3 秒转录）。
- **本地方案**：本机安装 `openai-whisper`，系统会自动调用本地模型。
- **无 Key 方案**：若未配置 ASR，系统会自动抽取平台视频简介与大纲生成基础事实卡片，绝不阻塞流程。

### Q3：Playwright 截图提示找不到浏览器怎么办？
在终端运行一行命令即可安装内置轻量 Chromium：
```bash
playwright install chromium
```

### Q4：原有的 WebApp（127.0.0.1:8787）还能继续用吗？
完全可以！底层数据结构与 API 保持兼容，既可以在 IDE 中用 Agent Skills 对话创作，也可以随时启动 `./start.sh` 打开 Web 大盘进行可视化浏览。
