# 素材与成稿契约 Schema(权威定义 · v2)

> 本文档是「素材包 → 成稿」结构化契约的**唯一权威定义**。
> `workflows/自媒体运营工厂.md`、`agent.md`、`skills/harsh-critic-skill`、`scripts/validate_materials_contract.py` 均以此为准。
> 契约目的:消除素材衰减、防虚构案例、让质量门可机器校验。

---

## 一、素材包条目 Schema(materials/YYYY-MM/<job_id>素材包.md)

每条素材以**单行**呈现,末尾必须带双标注,无标注视为无效条目(校验器不识别):

```
M1｜合同盲审代运行 29 元/单 vs 律所 500 元(2026-08 实测报价)（source_type: 真实数据 | priority: 核心）
```

| 字段 | 取值 | 含义 | 强制规则 |
|---|---|---|---|
| 条目编号 | `M1`~`Mn`(显式)/ `A1`~`An`(自动) | 唯一标识,供 consumed_materials 引用 | 显式编号优先;同包不可重复 |
| `source_type` | `真实数据` / `用户投喂` / `AI推断` | 来源三级标注 | **`AI推断` 严禁在成稿中作为事实引用,仅可作观点启发** |
| `priority` | `核心` / `辅助` | 冲击力权重 | 每包 **3-5 条 `核心`**,下游主编强制 100% 消费 |

**核心素材判定**:最有冲击力的具体数字/案例/Hook。核心条数不在 3-5 时,校验器 C1 直接 FAIL。

## 二、成稿 frontmatter Schema(outputs/<job_id>/<平台>/文案.md)

每篇定稿**首行必须是 frontmatter 块**(`---` 包裹),缺块即 C2 检查不通过:

```yaml
---
job_id: YYYY-MM-DD_主题名
platform: 小红书 | 公众号 | 短视频
consumed_materials: [M1, M3, M4]   # 实际引用的素材条目编号;核心素材必须 100% 在内
hook_formula: dbs-xhs-title #26     # 标题/开头公式编号;平台=小红书/公众号 时必填
---
```

| 字段 | 必填 | 校验规则 |
|---|---|---|
| `job_id` | ✅ | 必须等于 outputs 目录名 |
| `platform` | ✅ | 取值 ∈ {小红书, 公众号, 短视频} |
| `consumed_materials` | ✅ | 只含素材包内有效编号(C4 防假报关);核心素材 100% 引用(C3 素材衰减检测) |
| `hook_formula` | ✅(小红书/公众号) | 非空;违规开头由 C6 拦截 |

## 三、机器校验清单(scripts/validate_materials_contract.py)

| 检查 | 检测内容 | 级别 |
|---|---|---|
| C0 | 素材包定位 + schema 完整性 | WARN(legacy 降级) |
| C1 | 核心素材数量 3-5 条 | FAIL |
| C2 | 成稿 frontmatter 完整(含 hook_formula) | WARN/FAIL(strict) |
| C3 | 核心素材 100% 被实质引用(素材衰减检测) | FAIL |
| C4 | consumed_materials 无假报关编号;AI推断 引用告警 | FAIL/WARN |
| C5 | 数据密度:小红书/公众号 ≥2 个具体数字 | FAIL |
| C6 | 禁用 AI 腔开头句式 | FAIL |
| C7 | 油腻/违禁短语 | FAIL |

**退出码**:0 = 通过(允许 WARN);1 = 存在 FAIL(REJECTED)。

## 四、发布元数据 Schema(jobs/<job_id>/publish_log.json)

发布动作由 `scripts/publish_to_n8n.py --job-id <job_id>` 写入,数据回收由 `scripts/collect_post_stats.py` 追加 `records`,两脚本共用同一文件:

```json
{
  "job_id": "YYYY-MM-DD_主题名",
  "title": "笔记标题",
  "published_at": "2026-08-05 20:15:00",
  "platforms": ["小红书", "公众号"],
  "publish": [
    {"platform": "小红书", "status": "success", "at": "2026-08-05 20:15:00"}
  ],
  "records": [
    {"platform": "小红书", "collected_at": "2026-08-07 21:30:00",
     "reads": 5200, "likes": 260, "collects": 80, "comments": 15,
     "engagement": 0.068, "hit": true}
  ]
}
```

爆款阈值:阅读 ≥5000 或 点赞 ≥200(达到即触发范文解剖回填)。
