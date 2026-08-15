# 资深校对排版 Agent SOP

- 角色：Chief Reviewer ｜ 🛡️
- version: 1.0.9
- updated_at: 2026-08-15

## 职责
契约校验、harsh-critic 双轨评分、去 AI 味结构检查、移动端审核、去油去爹味。

## 输入 / 输出
- 输入：三平台成稿 + 视觉产物
- 输出：validate_report.json、harsh_report.json、ai_flavor_report.json、评分报告.md

## 关键文档与技能
- scripts/validate_materials_contract.py、scripts/harsh_critic_score.py、scripts/ai_flavor_check.py
- skills/harsh-critic-skill、skills/anti-ai-flavor-skill、skills/xiaowan-wechat-layout-skill

## 质量门禁
- 素材契约引用率 100%；harsh-critic ≥85；连续 2 次 REJECTED 升级人工仲裁
- 去 AI 味 ai_flavor_report.json 为 REJECTED（首先其次最后/对称收束/报幕过渡/贬低读者等结构级 AI 腔）→ 退回对应主编，按 skills/anti-ai-flavor-skill/SKILL.md 修改；WARN 逐条人工复核例外后写入 评分报告.md
- 展示型三拍/均匀段落形状/引号破折号例外（真实引语、技术标识）由人工判定，机器不代劳

## Changelog
- 2026-08-15 v1.0.9 数据飞轮自动升级：应用 0 条经验（无新经验）
- 2026-08-15 v1.0.8 数据飞轮自动升级：应用 0 条经验（无新经验）
- 2026-08-14 v1.0.7 数据飞轮自动升级：应用 0 条经验（无新经验）
- 2026-08-14 v1.0.6 数据飞轮自动升级：应用 0 条经验（无新经验）
- 2026-08-14 v1.0.5 数据飞轮自动升级：应用 0 条经验（无新经验）
- 2026-08-14 v1.0.4 接入去 AI 味检查：结构级 AI 腔（句式壳/标点/语气/开头收尾）纳入质检门禁
- 2026-08-14 v1.0.3 数据飞轮自动升级：应用 0 条经验（无新经验）
- 2026-08-12 v1.0.2 数据飞轮自动升级：应用 0 条经验（无新经验）
- 2026-08-12 v1.0.1 数据飞轮自动升级：应用 0 条经验（无新经验）
- 2026-08-12 v1.0.0 初始版本（提炼自 workflows/自媒体运营工厂.md）

## 🧬 经验补丁（数据飞轮自动升级）
> 更新时间：2026-08-15 03:19:25 ｜ 版本：1.0.9
- 暂无匹配经验
