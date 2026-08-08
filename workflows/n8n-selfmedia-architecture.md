# 自媒体 Agent + n8n 分发中枢整体架构方案

> ⚠️ **已废弃（2026-08-08）**：小红书账号风控禁止自动化工具写入，n8n 小红书自动发布链路（`xhs_publisher` / Playwright Worker / 三个小红书工作流）已全部下线并删除；公众号草稿改走官方 `draft/add` API。本文仅作历史架构参考，不再作为实施依据。

基于品牌内容营销操盘手 **@bbkirstry（小晚不在）** 的核心理念：“以个人 IP 为核、审美优先、通俗翻译、AI 放大人的判断力”。

---

## 一、 核心分工与边界（边界定义）

```text
┌───────────────────────────────────────────────────────────┐
│              思考与审美大脑 (Local Agent / CLI)             │
│  - 选题策划与洞见融入                                       │
│  - 文案撰写 (通俗化 + IP 风格)                              │
│  - 视觉卡片生成 (guizang-social-card-skill 3:4 比例)         │
│  - 公众号精细排版 (gzh-design-skill)                       │
│  - 人工审阅把关 (审美、品质、商业逻辑)                       │
└─────────────────────────────┬─────────────────────────────┘
                              │ 一键触发 Webhook (POST Payload)
                              ▼
┌───────────────────────────────────────────────────────────┐
│               分发与发布中枢 (NAS 端 n8n 引擎)              │
│  - Webhook 接收与 Payload 数据校验                          │
│  - 并行分发架构 (Parallel Worker Dispatch)                 │
│     ├── 分支 A: 小红书 Worker (Playwright 无头自动发布)    │
│     └── 分支 B: 微信公众号 API (自动草稿/发布)             │
│  - 状态汇总与通知 (企微/飞书机器人推送)                     │
│  - 结果归档 (飞书多维表格/Notion 数据日志)                   │
└───────────────────────────────────────────────────────────┘
```

---

## 二、 工作流具体执行步骤

### 阶段 1：本地创作与审核 (Local Agent)
1. 在 Local Agent / Antigravity 中运行指令：
   `主题「XXX」，做小红书 + 公众号双发`
2. Agent 自动调用 `guizang-social-card-skill` 生成小红书 3:4 高审美卡片卡片，同时调用 `gzh-design-skill` 生成公众号 HTML。
3. 你在本地进行预览与一键审核。

### 阶段 2：提交 n8n (Payload 结构)
审核通过后，Agent 向 NAS 端 n8n Webhook 触发 HTTP 请求：
- **URL**: `http://192.168.50.229:5678/webhook/publish-selfmedia`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "title": "爆款标题示例",
    "xhs_content": "小红书正文内容...",
    "gzh_html": "<h1>公众号 HTML 排版...</h1>",
    "images": [
      "/data/shared/slide1.png",
      "/data/shared/slide2.png"
    ],
    "tags": ["AI工具", "自媒体运营", "高效方法"]
  }
  ```

### 阶段 3：n8n 并行发布与通知
1. n8n 接收并校验数据无误后，分发至小红书与公众号发布分支。
2. 小红书 Worker 自动调起无头 Chromium 浏览器完成图文卡片上传、标题填写、正文填充与发布。
3. 微信公众号同步完成文章入库/发布。
4. 归档结果，向飞书/微信推送成功通知！

---

## 三、 已生成的 n8n 模板 JSON 文件

> 原小红书/公众号发布模板（`xhs_publish_v2/v3`、`xhs_gzh_immediate_publish`）已随自动化发布下线删除，不再提供。保留的 n8n 工作流仅有 `hot_topic_radar.json`（热点雷达）。
