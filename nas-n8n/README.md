# NAS 端 n8n + 热点雷达部署指南

本目录包含在 NAS（群晖 Synology / 威联通 QNAP / UNRAID / 极空间 / 绿联 / 任意 Linux Docker 环境）部署 **n8n 自动化工作流** 的完整配置。

> ⚠️ 小红书账号风控禁止自动化工具写入，**小红书自动发布 Worker（xhs_worker / xhs_publisher）已下线删除**；公众号草稿走官方 `draft/add` API（见项目根 README 4.2），不再依赖 NAS 浏览器自动化。

---

## 目录结构
```text
nas-n8n/
├── docker-compose.yml       # Docker Compose 核心服务配置文件
├── .env.example             # 环境变量配置模板
└── workflows/
    └── hot_topic_radar.json # 热点雷达工作流（RSSHub 抓取）
```

---

## 部署步骤

### 第一步：准备 NAS 目录与环境文件
1. 将 `nas-n8n` 文件夹上传到 NAS 的 `docker/n8n` 目录下。
2. 复制 `.env.example` 为 `.env`：
   ```bash
   cp .env.example .env
   ```
3. 修改 `.env` 中的 `N8N_HOST` 为你的 NAS 局域网 IP（例如 `192.168.1.100`），并修改 `POSTGRES_PASSWORD` 强密码。

---

## 第二步：一键启动 Docker 服务

### 选项 A：通过 SSH 命令行启动
```bash
cd /volume1/docker/n8n
docker-compose up -d
```

### 选项 B：通过群晖 Container Manager / Portainer
1. 打开群晖 **Container Manager** -> **项目 (Project)** -> **创建**。
2. 填入项目名称 `n8n-automation`，选择路径为上传的 `nas-n8n` 文件夹。
3. 拷贝 `docker-compose.yml` 内容并保存启动。

---

## 第三步：导入热点雷达工作流

```bash
python3 scripts/import_n8n_workflow_nas.py   # 导入 hot_topic_radar.json
python3 scripts/activate_n8n_workflows.py    # 激活全部工作流
```

访问 `http://<NAS_IP>:5678` 查看热点雷达工作流；发布环节不再位于 NAS（公众号走官方 API、小红书人工上传）。

---

## 常见问题处理
- **n8n 连不上 PostgreSQL**：等待 10-15 秒，PostgreSQL 容器健康检查通过后 n8n 会自动启动。
- **遗留 xhs_publisher 容器**：旧版本部署过小红书自动发布的 NAS 请执行 `docker compose rm -f xhs-publisher`（或 `docker rm -f xhs_publisher`）并删除 `shared_files/xhs_cookies.json`。
