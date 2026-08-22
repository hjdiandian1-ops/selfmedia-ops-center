# 项目交接说明（Antigravity 接手版）

> 这是给新 agent 的完整上下文。你没有之前的对话历史，读这份文档就能接手。
> 仓库：本地 `/Users/xiaowuliao/Projects/自媒体发布agent`，GitHub 远端 `hjdiandian1-ops/selfmedia-ops-center`。

---

## 0. 最重要的三件事（先读）

1. **你的第一任务是跑通测试。** 本仓库最近做了两轮较大重构（改动清单见第 2 节），但上一个执行环境装不了 fastapi，所以**完整 `pytest tests/ -q` 还没在本机跑过**。请先跑绿它，再谈其它。
2. **不要重复做第 2 节里已完成的事。** 那里列的都是已经落地并过语法检查的改动。
3. **`release/` 是发布快照，不是第二份源码。** 改主仓库代码后，要重跑 `python3 release/build_public_repo.py` 同步（机制见第 4 节）。

---

## 1. 项目是什么

一个本地自媒体的「选题 → 生产 → 质检 → 发布 → 数据复盘 → 经验反哺」运营平台。

- **后端**：FastAPI。入口 `webapp/server.py`（很薄，只挂载路由），共享层 `webapp/core.py`，业务路由在 `webapp/routers/`（overview / agents / viral / flywheel / topics / production / settings / publish / outputs / scheduler 共 11 个）。
- **前端**：`webapp/static/`（index.html + app.js + style.css），纯原生 JS，无打包工具。
- **脚本**：`scripts/`，多数是纯标准库（无第三方依赖），例如 `run_production.py`（生产流水线）、`fetch_source_content.py`（原文抓取）、`topic_feedback.py`（选题反馈）。
- **运行时数据**：`data/`（配置/飞轮/队列）、`jobs/`（生产任务）、`outputs/`（成品）、`materials/`（热点雷达/选题推荐）。
- **依赖**：见 `requirements.txt`（fastapi / uvicorn / pydantic / paramiko / requests / playwright / pytest），要求 Python 3.11+。

**启动命令**：
```bash
python3 -m uvicorn server:app --host 127.0.0.1 --port 8787 --app-dir webapp
# 或（如果根目录 start.sh 存在）./start.sh
```

---

## 2. 上一轮已完成的工作（勿重复）

### 2.1 后端改动

| 文件 | 做了什么 |
| :--- | :--- |
| `webapp/scheduler.py`（新） | 内置定时调度器，读 `data/scheduler.json`，按时间点后台触发选题抓取/爆款采集拆解/周聚合/48h 回收 |
| `webapp/routers/scheduler.py`（新） | `/api/scheduler` 的 GET/POST/run-now 三个接口 |
| `webapp/server.py` | 挂载 scheduler 路由 + 启动时拉起调度线程 |
| `webapp/core.py` | `_engine_status()` 返回引擎偏好模式与当前模型 |
| `webapp/routers/settings.py` | 引擎模式保存、token 用量返回、`/api/settings/llm-clear` 清空 LLM 配置 |
| `webapp/routers/production.py` | 生产队列按时间倒序 + 超 7 天标 `archived`、`/api/jobs` 倒序、`DELETE /api/production/{job_id}` 删除任务 |
| `scripts/llm_engine.py` | token 用量统计落盘 `data/llm_usage.json`、`engine_mode()` 读 `LLM_ENGINE_MODE` |
| `scripts/run_production.py` | ① Codex 生产主链路：`_prefer_codex()` / `_codex_generate()` / `_generate()`，5 个 LLM 调用点统一走 `_generate`（按引擎模式选 Codex 或 API，失败回退 API）；② `_research_grounding()` 注入真实原文/雷达/经验做素材 grounding；③ 删掉会编造数字的兜底模板；④ 修复文风指南截断错位（原来取 `[-1500:]` 尾部） |
| `scripts/fetch_source_content.py`（新） | 纯标准库抓原文正文（`extract_main_text` / `fetch_url_text` / `gather_grounding`），安全校验只抓公网 http/https |
| `scripts/topic_feedback.py` | 修复 `extract_topic_features()`：原来 `score_item("回填样本",1,theme,"",0.0)` 参数不匹配被静默吞掉、校准恒无效，已重写为正确调用 |
| `scripts/run_viral_analysis.py` | 拆解报告标注 `evidence_level`（content 真实 / title_only 推断），标题级推断在 MD 里加醒目提示 |

### 2.2 前端改动（都在 `webapp/static/index.html` 和 `app.js`）

- 设置页新增「定时任务」面板（启用开关、每任务添加/删除时间点、立即运行一次）。
- 设置页「AI 引擎」面板：引擎模式下拉（auto/api/codex/workbuddy）、当前模型、累计 token 用量、清空配置按钮。
- 生产队列：最新在前，超 1 周折叠进「已归档」`<details>`；选题页和队列都加了「删除」按钮。
- 采纳选题时把原文 link 透传给后端（`adopt(btn, title, link)`）。
- 爆款拆解报告弹窗显示「真实分析 / 推断拆解」徽标；数据飞轮/周经验包生成后 toast 写明写入路径和升级的 SOP 文件名。
- 数据页「质检趋势」「选题反馈模型」两个子面板补了功能说明文案。

### 2.3 文档与发布

| 文件 | 做了什么 |
| :--- | :--- |
| `README.md` + `release/templates/README.md` | 措辞对齐现状（「每日自动采集」→「设置→定时任务开启」；「优先 Codex」→「设置→AI 引擎显式选择」）；补截图 showcase、定时任务、引擎模式、token 用量说明 |
| `CONTRIBUTING.md` / `CHANGELOG.md` | 已在仓库（含 pre-commit 说明） |
| `scripts/generate_screenshot_placeholders.py`（新） | 纯 Python 生成 8 张占位截图（无第三方依赖） |
| `docs/screenshots/` | 8 张占位 PNG（00~07）+ 截图规范 README |
| `release/build_public_repo.py` | WHITELIST 补全（之前只打包单体 server.py，缺 routers/core/scheduler/topic_feedback/fetch_source_content/.github/截图等，会导致发布版断链） |
| `.pre-commit-config.yaml`（新） | 每次 commit 自动跑 `pytest tests/ -q` |
| `release/selfmedia-ops-center/` | 已重跑 build + `check_public_repo.py` 零泄露 + 干净 git 历史 |

> 说明：以上所有改动已通过 **Python AST 语法检查 + `node --check` + 纯标准库冒烟测试**，但没有跑过完整 pytest（上个环境缺 fastapi）。

---

## 3. 接下来要做的任务（按优先级）

### 任务 A（P0）：跑通完整测试套件

**目标**：`pytest tests/ -q` 全绿，修掉所有失败。

**步骤**：
1. 确认 Python 3.11+（本机 `.venv` 指向 mac aarch64 的 uv python，可用则用；否则自建 venv）。
2. `pip install -r requirements.txt`
3. 仓库根目录运行 `pytest tests/ -q`
4. 逐个修复失败。重点新改动相关测试：
   - `tests/test_fetch_source_content.py`（新，纯函数不触网）
   - `tests/test_topic_feedback.py`
   - `tests/test_suggest_topics.py`
   - `tests/test_run_production.py`
   - `tests/test_webapp_api.py`、`tests/test_qa_history_api.py`

**验收**：0 failed。不要删断言或弱化测试来"过"。

**注意**：`fetch_source_content.py`/`topic_feedback.py` 是纯标准库，可在无网环境跑纯函数测试；用 fastapi TestClient 的测试需要完整依赖，在本机 venv 里跑。

### 任务 B（P1）：Playwright 自动截图，替换 8 张占位图

**目标**：`docs/screenshots/` 下 8 张图换成真实界面截图（现在是占位图）。

**步骤**：
1. `python3 -m playwright install chromium`
2. 启动服务（见第 1 节启动命令）
3. 写 `scripts/capture_screenshots.py`：用 playwright 打开 `http://127.0.0.1:8787`，通过侧边栏 `.nav-item` 点击切视图（data-view 有：`overview` / `topics` / `themes` / `flywheel` / `pipeline` / `outputs` / `data`），逐视图截图。
   - `themes` = 爆款跟踪；`data` = 数据管理（内含质检趋势、选题反馈模型子页签）
   - 文件名与尺寸对齐 `docs/screenshots/README.md`：01~06 为 1920x1080，07 为 1920x720，00 建议录 GIF（1280x720）
4. 截图前处理：首次启动若弹「首启向导」遮罩先关掉/走完；切视图后等 1~2 秒；设 `device_scale_factor=2` 保证清晰。
5. 替换同名文件，脚本保留进仓库。

**验收**：8 张图是真实界面，GitHub README 渲染正常。

**注意**：截图依赖真实数据（选题/爆款/成品库有内容才好看），请在用户本机真实数据环境跑；空视图按 README 清单补。

### 任务 C（P1）：端到端冒烟验证

**目标**：确认最近改动的关键链路可用，输出验证报告。

**步骤**：
1. 启动服务。
2. 依次 curl 这些新/改接口，确认 200 且结构正确：
   - `GET /api/settings` → 应含 `llm.engine_mode`、`token_usage`、`engine.mode`
   - `POST /api/settings` body `{"llm_engine_mode":"api"}` → 保存后 GET 回显 api
   - `POST /api/settings/llm-clear` → GET `llm.configured` 变 false
   - `GET /api/scheduler` → 含 `config.tasks`（topics/viral/weekly/recycle）+ `tasks_meta`
   - `POST /api/scheduler` → 保存后回读一致；`POST /api/scheduler/run-now` body `{"task":"topics"}` → `status=started`
   - `GET /api/production/status` → queue 倒序、含 `age_days`/`archived`
   - `DELETE /api/production/<job_id>` → 队列和 jobs/、outputs/ 都被清（先建临时任务测，别删用户真实任务）
   - `GET /api/topics/feedback-report` → `report.markdown` 含「评分权重对比表」
   - `GET /api/qa/history` → 含 `trends`/`top_issues`/`milestones`
3. 若配了 LLM key，用 `POST /api/topics/adopt` 采纳一条选题，观察流水线走完（素材→初稿→视觉→质检→归档），确认 `jobs/<job_id>/production.log` 出现「使用 Codex CLI 生成」或正常 API 生成日志（取决于设置里的引擎模式）。
4. 把结果整理成一段报告（哪些通过、哪些报错、错误信息）。

**验收**：除「需要 LLM key / Pro 授权」的项外全部可用；出现 500/异常要定位根因并修复，不只记录。

### 任务 D（P2）：一致性收尾（几处小修）

1. `docs/screenshots/README.md` 第 9 行文件名是 `00-onboarding-demo.gif`，但仓库实际生成/引用的是 `00-onboarding-demo.png`，把它同步成 png（或注明「建议录 GIF，占位为 png」）。
2. **主仓库根目录缺 `start.sh`**（README 第六步写 `./start.sh`，但只有 `webapp/start.sh`）。在根目录补一个：
   ```bash
   cd "$(dirname "$0")" && exec python3 -m uvicorn server:app --host 127.0.0.1 --port "${1:-8787}" --app-dir webapp
   ```
   并 `chmod +x`；同时确认 `release/templates/start.sh` 一致。
3. 全文搜 `README.md` 与 `release/templates/README.md`，确认无残留「每日自动采集」「优先用 Codex」等与现状不符的措辞。
4. 核对 `release/build_public_repo.py` 的 WHITELIST 已含：`webapp/core.py`、`webapp/scheduler.py`、`webapp/routers/*.py`（11 个）、`scripts/topic_feedback.py`、`scripts/fetch_source_content.py`、`tests/test_topic_feedback.py`、`tests/test_fetch_source_content.py`、`.github/`、`CHANGELOG.md`、`CONTRIBUTING.md`、`docs/screenshots/*.png`、`.pre-commit-config.yaml`。缺失则补。

**验收**：以上 4 点一致；根目录 `./start.sh` 能直接启动。

---

## 4. 关键约束与注意

- **环境**：Python 3.11+。仓库里的 `.venv` 是指向 mac aarch64 的符号链接，在 Linux 容器里跑不了；用户本机 mac 上可用。
- **`release/` 同步机制**：主仓库 → `release/build_public_repo.py` → `release/selfmedia-ops-center/`。改主仓库代码后必须重跑它，否则发布版是旧的。跑之前可用 AST 解析 WHITELIST 检查源文件是否齐全。
- **安全**：发布前必须跑 `python3 scripts/security/check_public_repo.py --repo release/selfmedia-ops-center`，确认 0 泄露（.env、token、真实数据都不能进公开仓库）。
- **数据目录**：`jobs/`、`outputs/`、`materials/`、`data/` 是运行时数据，含用户真实内容，不要提交到公开仓库，也不要随意删除。
- **引擎模式语义**：`LLM_ENGINE_MODE` = `api`（强制 API 直连）/ `codex`（强制 Codex，不可用回退 API）/ `auto`（有 Codex 优先 Codex）/ `workbuddy`。生产流水线和爆款拆解都走这套。
- **原文抓取的已知局限**：小红书/抖音是 JS 动态页，`fetch_source_content.py` 抓不到正文时会静默降级（返回空），RSS 类源（36氪/IT之家/少数派）效果好。

---

## 5. 只能用户本人做（Agent 不要碰）

1. **README 第 9.5 节的 4 个 TODO**：面包多商品链接、客服微信二维码（docs/qr.png）、公众号/邮箱、企业版咨询——真实商业信息，只有用户能填。
2. **GitHub 首次推送**：`gh auth login` 配 token 后把 `release/selfmedia-ops-center/` 推送到远端（推送前再跑一次安全扫描）。
3. **Codex 模式实测**：需要用户本机的 codex CLI + 真实 LLM 凭据，在「设置 → AI 引擎」切 Codex 试生产一单。
4. **真实凭据**：公众号 AppID/Secret、LLM_API_KEY、代理等只填本地 `.env`，永不进仓库。
