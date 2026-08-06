# 自媒体发布 Agent 项目待办与路线图 (Roadmap & TODO)

---

## ✅ 已完成模块 (Completed)

1. [x] **基础设施搭建**：NAS 端部署 n8n + PostgreSQL + Playwright 小红书发布 Worker。
2. [x] **界面汉化与安全修复**：部署开源中文版 `blowsnow/n8n-chinese:latest`，解决 HTTP 局域网访问限制。
3. [x] **工作流模板自动化导入**：在 n8n 中一键导入小红书 + 公众号双平台发布工作流。
4. [x] **登录态持久化**：完成小红书创作者 Cookie 的格式解析与 NAS 同步挂载。
5. [x] **个人 IP 写作风格知识库**：建立 [personal-style-guide.md](file:///Users/xiaowuliao/Projects/%E8%87%AA%E5%AA%92%E4%BD%93%E5%8F%91%E5%B8%83agent/skills/personal-style-guide.md)，确立操盘手核心定位与黑白词汇名单。
7. [x] **“小吴聊”专属写作语料库提炼**：通过 [analyze_xiaowuliao_style.py](file:///Users/xiaowuliao/Projects/自媒体发布agent/scripts/analyze_xiaowuliao_style.py) 深度提炼 19 篇微信公众号历史发文，升级 [personal-style-guide.md](file:///Users/xiaowuliao/Projects/自媒体发布agent/skills/personal-style-guide.md)，确立了开篇 Hook、直爽实战口吻、经典标题公式与“三不原则”。
8. [x] **生图能力双轨渲染系统**：编写 [generate_ai_image.py](file:///Users/xiaowuliao/Projects/自媒体发布agent/scripts/generate_ai_image.py) AI 生图 API 连接器，与 3:4 HTML 视觉卡片 (`guizang-social-card-skill`) 形成【真实摄影/艺术插画封面 + 结构化知识卡片】双轨方案，并同步更新至 [agent.md](file:///Users/xiaowuliao/Projects/自媒体发布agent/agent.md)。
9. [x] **选题与热点雷达架构设计**：完成 RSSHub NAS 部署配置 [docker-compose-rsshub.yml](file:///Users/xiaowuliao/Projects/自媒体发布agent/nas-n8n/docker-compose-rsshub.yml)、飞书多维表格选题库结构规范 [FEISHU_TABLE_SCHEMA.md](file:///Users/xiaowuliao/Projects/自媒体发布agent/nas-n8n/FEISHU_TABLE_SCHEMA.md) 以及 n8n 热点雷达工作流 [hot_topic_radar.json](file:///Users/xiaowuliao/Projects/自媒体发布agent/nas-n8n/workflows/hot_topic_radar.json)。
10. [x] **小吴聊爆款图文与短视频 Skill 集成**：将 [viral-content-skill](file:///Users/xiaowuliao/Projects/自媒体发布agent/skills/viral-content-skill/SKILL.md) 引入 Agent 体系，新增 【硬核拆解】/【商业对话】/【商业观察】 三大爆款视角与 120s 短视频黄金分镜脚本流程 [video-script.md](file:///Users/xiaowuliao/Projects/自媒体发布agent/workflows/video-script.md)。
11. [x] **「自媒体运营工厂」Teamwork 拟真报社岗位架构升级**：将原线性流程全面重构为基于 Teamwork 多 Agent 协同的「自媒体运营工厂」[自媒体运营工厂.md](file:///Users/xiaowuliao/Projects/自媒体发布agent/workflows/自媒体运营工厂.md)，确立了总编、资深采编、小红书主编、公众号主编、短视频导演、美术总监、资深校对排版、归档发布员 8 大岗位分工，并引入定稿后强制自动清扫 process_* 中间过程临时文件的清理机制。

---

- [ ] **【重点待办 1】第一篇真实选题端到端创作实战**
  - **拟定选题**：《全网首发：我的 NAS + AI 自媒体全自动发布系统搭建全过程》
  - **目标**：在 Agent 对话中触发创作 ➔ 生成 3:4 视觉卡片/AI 封面与公众号 HTML ➔ 人工确认 ➔ 输入“确认发布”一键分发到小红书。
- [ ] **【待办 2】全网热点聚合替代方案探索** (暂跳过)
  - **说明**：暂时跳过泛快讯抓取，后续根据需求评估寻找更契合的头部源或自动化热点方案。


