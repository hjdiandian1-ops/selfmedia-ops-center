# Workbuddy 交接说明(自媒体运营工厂 · 执行手册)

> 给接手的 Agent(workbuddy/Reasonix 等)的自包含说明:**拿到本仓库后,如何按标准产出内容并自检**。
> 核心三文档(必读,按序):
> 1. [产出标准.md](file:///Users/xiaowuliao/Projects/自媒体发布agent/workflows/产出标准.md) — 成果规格与验收清单(照此产出)
> 2. [contract-schema.md](file:///Users/xiaowuliao/Projects/自媒体发布agent/workflows/contract-schema.md) — 素材包/成稿数据契约(机器可校验)
> 3. [自媒体运营工厂.md](file:///Users/xiaowuliao/Projects/自媒体发布agent/workflows/自媒体运营工厂.md) — 报社岗位 SOP(8 角色分工)

---

## 一、项目是什么

「小吴聊」个人 IP 的自媒体内容生产系统:选题 → 素材包 → 三平台创作(小红书/公众号/短视频)→ 质检 → 落盘 → 发布(发布走 NAS,本地只备好产物)。

## 二、拿到项目后做什么(执行顺序)

1. **读文档**:先读上面三份(产出标准 > 契约 > SOP),确认「成果长什么样、怎么自检」。
2. **看现状**:`python3 scripts/run_daily_pipeline.py --recycle`(有无待回收)、`python3 scripts/job_state.py list`(进行中 Job)、`ls outputs/`(已有产出样例)。
3. **按用户指令创作**:用户给出主题 → 走下面「一次创作的标准流程」。
4. **自检并交付**:按「产出标准.md 第七章自检清单」逐条打勾,全绿才交付。

## 三、一次创作的标准流程

```
① 选题:用户指定主题 或 运行 python3 scripts/suggest_topics.py 取推荐
        → python3 scripts/job_state.py init <YYYY-MM-DD_主题名> --theme "主题"
② 素材:资深采编产出素材包 materials/YYYY-MM/YYYY-MM-DD_主题素材包.md
        (每条素材带 source_type|priority 双标注,3-5 条核心)
③ 创作:小红书主编(文案+3:4卡片 HTML+PNG截图)/ 公众号主编(长文+排版HTML)
        成稿带 frontmatter 契约(consumed_materials 核心 100% 引用)
        落盘 outputs/YYYY-MM-DD_主题名/{小红书,公众号}/ (短视频选配)
④ 质检(必跑,两条命令):
        python3 scripts/validate_materials_contract.py outputs/<job_id>/ --out outputs/<job_id>/validate_report.json
        python3 scripts/harsh_critic_score.py      outputs/<job_id>/ --out outputs/<job_id>/harsh_report.json
        要求:validate=PASSED、harsh ≥85、素材引用率=100%;不达标退回重写(最多2次,第3次请用户仲裁)
⑤ 落盘与清扫:三级目录整洁、删除 process_* 临时文件
        → python3 scripts/job_state.py set <job_id> archive --note "质检通过"
⑥ 发布(人工终审;小红书禁止自动化工具写入):
        公众号草稿(官方 API,需 GZH_APP_ID/SECRET):
        python3 scripts/gzh_draft_api.py --title "标题" --content-file outputs/<job_id>/公众号/<排版.html> --cover outputs/<job_id>/小红书/封面.png --author "小吴聊" --job-id <job_id>
        小红书(人工上传):直接使用 outputs/<job_id>/小红书/ 产出文件夹
        手机/网页端手动上传发布后标记记录:
        python3 scripts/record_manual_publish.py <job_id> --platform 小红书
```

## 四、关键命令速查

| 命令 | 作用 |
|---|---|
| `python3 scripts/job_state.py list / show <job_id>` | Job 状态机 |
| `python3 scripts/run_daily_pipeline.py --topics --auto-select` | 热点→选题→自动建 Job |
| `python3 scripts/run_daily_pipeline.py --qa outputs/<job_id>/` | 质检链(契约+评分) |
| `python3 scripts/run_daily_pipeline.py --recycle / --weekly` | 48h 回收检查 / 周报 |
| `bash webapp/start.sh` | 启动工作台 WebUI(http://127.0.0.1:8787,产出预览在 Job 详情) |
| `python3 scripts/gzh_draft_api.py ...` | 公众号草稿(官方 draft/add API) |
| `python3 scripts/record_manual_publish.py <job_id> --platform 小红书` | 小红书手动发布后标记记录 |

## 五、环境限制与降级(重要)

| 情况 | 处理 |
|---|---|
| **生图 API 无 key**(NAS 离线/gemini 额度耗尽) | 封面用 HTML 卡片截图(`scripts/render_card_to_image.py`,本地 playwright),不做 AI 艺术封面 |
| **NAS/RSSHub 离线** | 热点用最近雷达 + WebSearch 降级;公众号草稿走官方 API 不受影响,小红书始终人工发布 |
| **素材不足/无种子素材** | 严禁脑补虚构:向用户索取,或只做观点启发(AI推断 素材不得当事实) |
| **同一问题失败 3 次** | 立即停止重试,向用户说明并请求换方向(铁律,防 token 浪费) |

## 六、质量标准(一句话)

> 素材不衰减(核心素材 100% 进成稿)、数字要真实(官方来源)、开头要 Hook(不用 AI 腔)、视觉要达标(3:4 卡片 1080×1440、无孤行)、机器自检全绿才交付。
