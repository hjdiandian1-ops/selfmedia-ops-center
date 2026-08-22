# 贡献指南 (Contributing Guide)

感谢你关注并愿意为 **selfmedia-ops-center (自媒体运营工厂)** 贡献代码与内容！

无论是修复 Bug、新增信息源、改进 Agent Prompt、优化前端主题，还是补充文档，我们都非常欢迎。请在提交前阅读本指南。

---

## 🧭 目录

1. [快速上手开发环境](#-1-快速上手开发环境)
2. [代码风格与规范](#-2-代码风格与规范)
3. [Git 提交信息规范](#-3-git-提交信息规范)
4. [Pull Request (PR) 流程](#-4-pull-request-pr-流程)
5. [首次贡献推荐 (Good First Issues)](#-5-首次贡献推荐-good-first-issues)
6. [社区守则与安全策略](#-6-社区守则与安全策略)

---

## 🛠️ 1. 快速上手开发环境

### 前置要求
- Python 3.9+ (推荐 3.11 或 3.13)
- Git
- 现代浏览器 (Chrome / Safari / Edge / Firefox)

### 步骤

```bash
# 1. Fork 本仓库到你的 GitHub 账号，然后 Clone 到本地
git clone https://github.com/<your-username>/selfmedia-ops-center.git
cd selfmedia-ops-center

# 2. 创建并激活虚拟环境 (可选但推荐)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装开发与测试依赖
pip install -r requirements.txt
pip install pytest flake8

# 4. 启动本地开发服务 (绑定本地 127.0.0.1:8787)
python3 webapp/server.py

# 5. 运行完整自动化测试套件
pytest -v tests

# 6. （推荐）安装提交前检查：每次 git commit 自动跑 pytest，失败即阻止提交
pip install pre-commit && pre-commit install
```

---

## 🎨 2. 代码风格与规范

本项目追求**极简、轻量、高可维护性**（零重型框架依赖，前端为纯原生 Vanilla JS + CSS 变量体系，后端为 FastAPI 模块化路由）。

### Python 后端规范
- **代码缩进**：统一使用 **4 个空格**，禁止制表符 (Tab)。
- **编码格式**：所有 Python 文件顶部声明 `# -*- coding: utf-8 -*-`。
- **命名规范**：
  - 模块与文件名：`snake_case.py` (如 `topic_feedback.py`)
  - 函数与变量：`snake_case()`
  - 类名：`PascalCase` (如 `AdoptTopicRequest`)
  - 常量：`UPPER_SNAKE_CASE` (如 `DAILY_FRESH_W`)
- **类型提示与 Docstring**：对外核心函数与 API 接口须包含明确类型注解及函数说明文档。
- **配置一致性**：参考根目录下 [`pyproject.toml`](./pyproject.toml) 中的 `pytest` 与路径配置。

### 前端规范 (Vanilla JS & CSS)
- **零外部打包工具**：不使用 Webpack/Vite 等编译工具，纯浏览器原生解析。
- **CSS 变量体系**：颜色与间距须调用 `var(--primary)`、`var(--surface)`、`var(--radius-md)`，保证 8 套主题无缝适配。
- **安全性防护**：动态注入 HTML 时必须经过 `escapeHtml()` 处理，禁止未经清洗的原始用户输入拼接。

---

## 📦 3. Git 提交信息规范

本项目遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范，请使用「**类型: 中文简述**」格式：

```
<type>(<scope>): <subject>
```

### 常用 Type 类型
| Type | 说明 | 示例 |
| :--- | :--- | :--- |
| `feat` | 新增功能或模块 | `feat(topics): 新增知乎热榜 RSS 抓取解析器` |
| `fix` | 修复缺陷或错误 | `fix(qa): 修复 Harsh Critic 分数计算边界异常` |
| `docs` | 仅文档变更 | `docs: 补充 8 套主题视觉设计与配置说明` |
| `style` | 不影响代码运行的格式/UI样式微调 | `style(mobile): 优化窄屏下表格横向滚动体验` |
| `refactor` | 重构（既不修复 bug 也不添加特性的代码更改） | `refactor(server): 拆分巨型单体为模块化 Router` |
| `test` | 新增或修改测试用例 | `test(e2e): 补充选题采纳到归档全链路自动化测试` |
| `perf` | 性能优化 | `perf(stats): 优化大批量历史任务扫描性能` |

---

## 🚀 4. Pull Request (PR) 流程

1. **新建分支**：
   ```bash
   git checkout -b feat/add-zhihu-rss-source
   ```
2. **本地编码与验证**：
   - 编写整洁、可读的代码；
   - 编写对应的测试文件（存放在 `tests/test_*.py`）；
   - 运行并确保所有测试 100% 通过：
     ```bash
     pytest -v tests
     ```
3. **提交与推送**：
   ```bash
   git commit -m "feat(topics): 新增知乎热点信息源支持"
   git push origin feat/add-zhihu-rss-source
   ```
4. **发起 PR**：
   - 在 GitHub 上发起 Pull Request 到 `main` 分支；
   - 填写 PR 模板中的改动说明与自测结果。

---

## 🌟 5. 首次贡献推荐 (Good First Issues)

如果你是第一次参与开源贡献，可以从以下适合新手的任务开始：

1. **新增公开热点 RSS 信息源**
   - 目标：在 `scripts/fetch_hot_topics.py` 中增加 V2EX / 少数派 / 虎嗅等科技热点 RSS 解析器。
2. **新增一套高审美主题配色**
   - 目标：在 `webapp/static/style.css` 中基于现有 CSS 变量扩展（如「莫兰迪灰蓝」「极简包豪斯」）。
3. **补充长文风格模板 (Style Presets)**
   - 目标：在 `data/templates/style_docs/` 下增加如「硬核科技白皮书」「财经深度研报」文风模板。
4. **移动端/窄屏操作微调**
   - 目标：进一步优化小屏手机下某些复杂模态框的触控体验。
5. **去 AI 味规则词库扩展**
   - 目标：在 `scripts/ai_flavor_check.py` 扩充行业常见空话套话检测词。
6. **文档与使用教程完善**
   - 目标：完善各平台（小红书/公众号/视频号）发布 SOP 指南与 FAQ。

---

## 🛡️ 6. 社区守则与安全策略

- **绝不提交机密信息**：严禁将任何个人的 API Key、OAuth 密钥、微信 AppSecret 或个人隐私数据提交至仓库（本地运行请配置在 `.env` 或 `data/settings.json` 中）。
- **安全漏洞报告**：发现安全漏洞请阅读 [`SECURITY.md`](./SECURITY.md)，通过私密渠道提交。
- 友善交流，尊重每一位参与者的建议与时间！
