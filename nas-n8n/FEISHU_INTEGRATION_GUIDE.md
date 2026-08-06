# 📖 飞书自建应用与多维表格 (Feishu Base) 5 步接入指南

通过飞书自建应用，我们可以让 NAS 端 n8n 自动将 RSSHub 抓取并经 AI 提炼的全网爆款热点，**静默写入你的飞书多维表格（选题库）**，并向你的飞书发送图文卡片通知。

---

## 🛠️ 第一步：在飞书开放平台创建自建应用

1. 访问 **[飞书开放平台开发者后台](https://open.feishu.cn/app/)** 并使用飞书账号登录。
2. 点击 **“创建企业自建应用”**。
   - **应用名称**：`小吴聊选题雷达`
   - **应用描述**：自媒体全网爆款选题抓取与 AI 提炼写入
   - **应用图标**：上传任意极客风格图标

---

## 🔑 第二步：获取 API 凭证 (App ID & App Secret)

1. 创建成功后，进入应用的 **“凭证与基础信息”** 页面。
2. 复制并保存以下两个重要 Key（后面填入 n8n 节点）：
   - `App ID`（例如：`cli_a1b2c3d4e5f6xxxx`）
   - `App Secret`（例如：`WXYZ1234abcd5678efgh....`）

---

## 🔐 第三步：开通多维表格与机器人权限

1. 在左侧菜单点击 **“权限管理”**。
2. 在搜索框中依次搜索并勾选开通以下权限：
   - `bitable:app` 或 `查看、编辑多维表格`（用于向表格新增记录）
   - `im:message:send_as_bot` 或 `以机器人身份发送消息`（用于发送飞书消息卡片）
3. 在左侧菜单点击 **“应用功能” -> “机器人”**，点击 **“启用机器人”** 功能。
4. 在左侧菜单点击 **“版本管理与发布” -> “创建版本”**：
   - 填入版本号（例如 `1.0.0`）与更新说明，点击提交发布（企业自建应用通常秒过）。

---

## 📊 第四步：新建多维表格并添加应用协作者

1. 打开电脑端或手机端飞书，新建一个**多维表格**，命名为 **`【小吴聊】爆款选题雷达库`**。
2. 按照 [FEISHU_TABLE_SCHEMA.md](file:///Users/xiaowuliao/Projects/自媒体发布agent/nas-n8n/FEISHU_TABLE_SCHEMA.md) 创建字段：
   - `选题标题` (单行文本)
   - `来源平台` (单选)
   - `爆款热度分` (数字)
   - `AI 核心摘要` (多行文本)
   - `推荐创作方向` (多选)
   - `适用平台` (多选)
   - `选题状态` (单选：`🆕 待筛选` / `📌 已采纳` / `✍️ 创作中` / `✅ 已发布`)
   - `原始链接` (超链接)
3. **⚠️ 最关键一步**：点击多维表格右上角的 **“分享/协作”** 按钮 ➔ 搜索刚才创建的应用名称 **`小吴聊选题雷达`** ➔ 设置权限为 **“可编辑”**！（若不添加协作者，自建应用将无权限写入此表格）。
4. 从多维表格的浏览器 URL 地址栏中复制 `App Token` 和 `Table ID`：
   - URL 示例：`https://xxxx.feishu.cn/base/app_token_123456?table=tbl_789012`
   - `app_token` = `app_token_123456`
   - `table_id` = `tbl_789012`

---

## ⚡ 第五步：在 n8n 中配置自动写入 HTTP 节点

n8n 会通过以下两个标准 API 自动完成写入：

### 1. 获取临时访问令牌 (tenant_access_token)
- **POST**: `https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal`
- **Body**:
  ```json
  {
    "app_id": "你的_APP_ID",
    "app_secret": "你的_APP_SECRET"
  }
  ```

### 2. 自动新增多维表格记录
- **POST**: `https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records`
- **Header**: `Authorization: Bearer {tenant_access_token}`
- **Body**:
  ```json
  {
    "fields": {
      "选题标题": "={{ $json.title }}",
      "来源平台": "36Kr/RSS",
      "爆款热度分": 88,
      "AI 核心摘要": "={{ $json.summary }}",
      "推荐创作方向": ["AI工具测评"],
      "适用平台": ["小红书", "公众号"],
      "选题状态": "🆕 待筛选",
      "原始链接": "={{ $json.url }}"
    }
  }
  ```
