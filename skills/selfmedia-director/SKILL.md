---
name: selfmedia-director
description: 自媒体总编·总控调度与四重质检门禁｜负责全流程任务调度协调、素材契约校验、Harsh Critic 80分红线把关、22条去AI味硬性过滤与合规审核。
dependency:
  python:
    - pytest>=7.0.0
license: MIT
---

# 🎯 自媒体总编·总控调度与四重质检门禁 (selfmedia-director)

作为整个自媒体运营套件的「总指挥官」，负责端到端流程推进与最严苛的质量守门。

---

## 🛡️ 四重质检门禁（全部通过方可放行）

1. **Gate 1: 素材事实契约 (Materials Contract)**
   - 检查是否有量化数据支撑、是否有明确出处/来源、是否有清晰的受众冲突点。
2. **Gate 2: Harsh Critic 80分红线 (Harsh Critic)**
   - 从挑剔读者视角打分：首屏抓人度、干货信息增量、叙事结构起伏、互动转化。总分低于 80 分坚决打回！
3. **Gate 3: 去 AI 味 22 条硬性规则 (Anti-AI Flavor)**
   - 严禁“在这个时代/总而言之/显而易见/毫无疑问/双刃剑”等套话，AI味系数超标立即拦截。
4. **Gate 4: 广告法与平台合规门禁 (Compliance Review)**
   - 零容忍极限词（最/第一/独家）、投资收益承诺及违规导流话术。

---

## 🛠️ CLI 命令行质检验收

```bash
# 对生成的文案执行全套四重门禁质检
python3 -m selfmedia.quality.check --file output.md
```
