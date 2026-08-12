---
job_id: 2026-08-13_xAI发布Grok Bo
schema_version: materials/v1（source_type 三级标注 + priority 核心标记）
归档时间: 2026-08-13
录入岗位: 资深采编 Agent
专栏视角: 【商业观察】
合规说明: 选题源自推楼1号/X 海外热点，已有多家中英媒体同步报道（The Verge/VentureBeat/IT之家/界面），国内可合规发布；关键事实已对照多家来源交叉核验。
---

# 📦 素材资产库：xAI 发布 Grok Bot「云端 AI 同事」素材包

**分类**：#AI智能体 #Grok #xAI #Cursor #企业软件 #商业观察

---

## 🔍 一、 对标拆解 (dbs-benchmark)

- **痛点对标**：8 月 11 日（美东）xAI/SpaceXAI 发布 Grok Bot 早期 beta——AI 从「回答问题」跨到「云端同事」：登录你的工具、跨应用干活、合盖照跑。主流报道都在复述「又一个 agent」，很少有人回答：120 美元/月起雇一个 AI 同事，账怎么算？权限怎么隔离？人的什么能力会因此变贵？（source_type: AI推断 | priority: 辅助）
- **差异化切入点**：用「账本」结构拆三笔账——订阅定价账（120/200/300 美元三档 + 超量按 token）、资本账（600 亿美元收购 Cursor）、稀缺品账（执行成本趋零后，判断/流程定义/信任变贵）。本文不吹不黑，给机制、给权限边界、给行动判断。（source_type: AI推断 | priority: 辅助）

---

## 🛠️ 二、 核心素材与数据清单

- **M1｜发布与定价梯次：个人 200 美元/月、团队每席 120 美元/月、Heavy 300 美元/月**：xAI（现已并入 SpaceX，对外称 SpaceXAI）于 2026 年 8 月 11 日（美东）发布 Grok Bot 早期 beta；首批开放 Cursor Ultra（个人 200 美元/月，约合 1400 元）、SuperGrok Heavy（300 美元/月，约合 2100 元）、Cursor Premium Teams（每席位每月 120 美元，约合 840 元），已订用户不另付费；支持 macOS/Windows/Linux/iOS，Android 即将上线，企业客户进候补名单；套餐含每周使用额度，超出按 token 计费。（source_type: 真实数据 | priority: 核心）
  - 来源：https://venturebeat.com/orchestration/spacexais-grok-bot-turns-agents-into-persistent-digital-coworkers-that-can-operate-your-apps-for-120-per-month（VentureBeat 2026-08-11）；https://www.sohu.com/a/1061937153_122014422（搜狐/网易智能 2026-08-12）
- **M2｜600 亿美元收购 Cursor 后的首个企业级 agent 产品**：SpaceX 于 2026 年 6 月以 600 亿美元收购 AI 编程公司 Cursor；Grok Bot 直接挂在 Cursor 订阅体系内，源自内部代号「Sandra」的原型。每个 Bot 拥有独立云端电脑，可登录用户常用的 App/网站/收件箱，像人类同事一样操作界面完成多步任务；同一用户创建的多个 Bot 共用一台长期在线的云电脑，共享文件、浏览器与登录状态，可接力交接。（source_type: 真实数据 | priority: 核心）
  - 来源：https://www.theverge.com/ai-artificial-intelligence/978666/spacexai-grok-bot-ai-agent-beta-launch（The Verge 2026-08-11）；https://www.ithome.com/0/988/570.htm（IT之家 2026-08-12）；https://news.sbs.co.kr/english/article.do?news_id=N1008701627（SBS 英文 2026-08-11）
- **M3｜24 小时在线 + 无需 API：演示一次即记住流程**：Grok Bot 在云端持续运行，用户合上电脑任务照跑；官方称可操作「没有干净 API 或 MCP」的网站与应用。用户示范一遍操作，Bot 即保存为可复用 routine，并可吸收修正持续进化；多个 Bot 能互相传上下文、在群聊里自分工、转交工作，内部已用 Sales Outbound、Talent Scout、Paid Media、Expense Manager、Chief of Staff 等 8 类岗位 Bot 跑通销售外呼、营销、办公运营与 bug 修复。（source_type: 真实数据 | priority: 核心）
  - 来源：https://venturebeat.com/orchestration/spacexais-grok-bot-turns-agents-into-persistent-digital-coworkers-that-can-operate-your-apps-for-120-per-month（VentureBeat 2026-08-11）；https://www.sohu.com/a/1061937153_122014422（搜狐/网易智能 2026-08-12）
- **M4｜安全与权限争议：共享登录状态、Auto-review 人工授权**：多个 Bot 共用同一云电脑意味着登录状态与部分权限按「用户」而非按「单个 Bot」隔离——一个 Bot 登录过的网站，另一个可直接接手；xAI 提供 Auto-review 机制，在支付、敏感操作或 Bot 判断不确定时弹卡请求人工授权。海外媒体已用「Grok Bot 想要你的密码」作标题讨论该取舍。（source_type: 真实数据 | priority: 核心）
  - 来源：https://www.sohu.com/a/1061937153_122014422（搜狐/网易智能 2026-08-12）；https://www.news18.com/tech/xais-grok-bot-wants-your-passwords-the-ai-agent-that-logs-into-your-accounts-and-works-while-you-sleep-10268837.html（News18 2026-08-11）
- **M5｜Grok 4.6 发布：API 每百万输入 token 2 美元、每百万输出 token 6 美元**：2026 年 8 月 12 日（北京时间）SpaceXAI 发布 Grok 4.6，官方定位为强化长时间运行的智能体任务，今日已在 Cursor 与 Grok Build 上线，也可通过 API 及 OpenRouter、Vercel、Cloudflare 调用；API 定价每百万输入 token 2 美元、每百万输出 token 6 美元，支持 50 万上下文。（source_type: 真实数据 | priority: 核心）
  - 来源：https://www.jiemian.com/article/14914370.html（界面新闻 2026-08-12）；https://cursor.com/cn/blog/grok-4-6（Cursor 官方博客 2026-08-12）；https://openrouter.ai/x-ai/grok-4.6（OpenRouter 模型页）

---

## 📎 三、 辅助素材

- **A1｜竞争格局：五大厂同一赛道开打**：Grok Bot 对标 OpenAI ChatGPT Work、Anthropic Claude Cowork、微软 Copilot Tasks、谷歌 Gemini Enterprise Agent；业界已有「SaaS-pocalypse（SaaS 末日论）」的讨论。xAI 此前在智能体市场被认为掉队，此次发布被多家媒体解读为追赶反击。（source_type: 真实数据 | priority: 辅助）
  - 来源：https://www.ithome.com/0/988/570.htm（IT之家 2026-08-12）；https://news.sbs.co.kr/english/article.do?news_id=N1008701627（SBS 英文 2026-08-11）
- **A2｜内部原型转产品**：Grok Bot 最早是 xAI 内部原型，先在销售外呼、营销投放、办公运营、bug 修复等场景跑通，随后扩散到全公司，再把内部工作流产品化对外。（source_type: 真实数据 | priority: 辅助）
  - 来源：https://www.theverge.com/ai-artificial-intelligence/978666/spacexai-grok-bot-ai-agent-beta-launch（The Verge 2026-08-11）
- **A3｜首批口碑与批评**：Lenny Rachitsky 提前体验后称「好久没对 AI 新品这么兴奋，像 OpenClaw 但更易用、更可靠、没那么吓人」；Matt Shumer 测试数周称「它是 everything 的 agent，不只是代码」，主要批评是模型由后端自动路由、用户无法自选模型，且官方未发布任何 agent 性能基准。（source_type: 真实数据 | priority: 辅助）
  - 来源：https://venturebeat.com/orchestration/spacexais-grok-bot-turns-agents-into-persistent-digital-coworkers-that-can-operate-your-apps-for-120-per-month（VentureBeat 2026-08-11）
- **A4｜马斯克表态：AI 将占 SpaceX 价值 99%**：马斯克在 SpaceX 财报电话会上称，大约再过四五年，AI 将占到 SpaceX 价值的 99%；SpaceX 正在把「太空+AI」叙事变成公司转型主线。（source_type: 真实数据 | priority: 辅助）
  - 来源：https://www.ithome.com/list/2026-08-12.html（IT之家新闻列表 2026-08-12）
- **A5｜行为记忆与主动性**：官方称 Bot 会保留任务上下文、学习用户写作口吻与边界案例，能续接中断的对话、提醒停滞的交接，并随时间变得更主动——「在你开口前就把活捡起来」。（source_type: 真实数据 | priority: 辅助）
  - 来源：https://www.theverge.com/ai-artificial-intelligence/978666/spacexai-grok-bot-ai-agent-beta-launch（The Verge 2026-08-11）

---

## 💥 爆款 Hook 语料库（已过 style-guide 黑白名单校验）

- **H1（数字冲击）**：「600 亿美元收购 Cursor 之后，马斯克开始卖『AI 同事』：120 美元/月，24 小时在线，替你登录账号干活。」
- **H2（身份代入）**：「当你的 AI 同事能自己登录系统、跨应用把活干完，你手里还剩哪件事是它替不了的？」
- **H3（认知冲突）**：「AI 同事越便宜，人的判断越贵——Grok Bot 真正在卖的，不是自动化，是一个新的管理隐喻。」
