# 去 AI 味开源调研与整合说明

> 更新：2026-08-14 ｜ 用途：为工作台质检链补充“结构级 AI 腔”检测，与既有 harsh-critic（营销号词汇/爹味/禁用开头）形成互补。

## 一、调研结论（选型）

中文去 AI 味项目很多，但大多数是“提示词模板”或“改写器”，无法嵌入我们的机器质检链。最终选取 **3 个项目**作为规则来源：

| 项目 | 形态 | 许可 | 选入理由 |
|---|---|---|---|
| [zero-click/avoid-ai-writing-zh](https://github.com/zero-click/avoid-ai-writing-zh) | 写作规避清单（Markdown） | MIT | 中文 AI 腔模式最全，覆盖“不是而是、三拍结构、报幕式过渡、对称收束”等结构级模式 |
| [liuliu-66-create/ll-humanizer-zh](https://github.com/liuliu-66-create/ll-humanizer-zh) | 去 AI 味硬规则 Skill | 以仓库 LICENSE 为准 | 规则最激进可执行：禁正文引号、禁修辞破折号、禁老师式自问自答、禁替读者说话 |
| [B1lli/remove-ai-flavor-writing-skill](https://github.com/B1lli/remove-ai-flavor-writing-skill) | Codex Skill | 以仓库 LICENSE 为准 | 按“壳”分类（二元对比壳/阶段序列壳/本质断言/助手路线标记），可直接转正则 |

> 许可说明：zero-click 项目已确认 MIT；另两项目本次整合时未重新核验 LICENSE（网络受限），仅引用其公开规则并注明出处。本工作台整合产物 `skills/anti-ai-flavor-skill/` 与 `scripts/ai_flavor_check.py` 为原创实现，规则出处逐条标注。

## 二、未选但可补充的项目（备选池）

- LifelongLazyLearner/qu-ai-wei（去 AI 味词库）
- ninehills/public-skills 中的 deslop-zh（中文去 AI 味 Skill）
- hongcha1101/de-aigc-ch（改写器）
- 0xtresser/cn-humanizer、Show-Chan97/Humanizer-zh、moli238/humanizer-zh-moli（改写方向）
- slivenred/no-ai-slop-zh-TW（繁体/港台腔）
- hardikpandya/stop-slop（英文 slop 词库）

备选池暂不并入：改写器类与“流水线成稿”场景冲突（我们要的是审核而非改写），英文/繁体词库与当前三平台中文成稿匹配度低。

## 三、整合原则

1. **分层**：词汇层（营销号套话、爹味、禁用开头）继续由 `harsh_critic_score.py` 负责；结构层（三拍、对称、报幕、壳结构）由新增 `ai_flavor_check.py` 负责，避免重复扣分。
2. **机器可算 + 人工复核**：脚本只做可解释的初筛（PASSED / WARN / REJECTED + 命中位置），每条命中标注规则来源项目；最终判断由资深校对排版人工复核。
3. **阈值保守**：真实人类写作也会偶尔出现“本质上”“值得注意的是”，脚本按次数分级（1 次 WARN、≥3 次 REJECTED），不搞“见词就杀”。
4. **例外明确**：正文引语、真实采访、产品/API 名称中的引号与连字符属于例外，脚本给出建议而不是一刀切。

## 四、落地位置

- 规则文档：`skills/anti-ai-flavor-skill/SKILL.md`
- 机器初筛：`scripts/ai_flavor_check.py` → 输出 `ai_flavor_report.json`
- 质检链：`run_daily_pipeline.py --qa` 第 3 步（harsh-critic 之后、compliance 之前）
- 评分报告：`评分报告.md` 新增“去 AI 味”小节
- 角色 SOP：`agents/reviewer-资深校对排版.md` 将本检查列为质量门禁之一
