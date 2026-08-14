# 素材包契约 Schema（通用版）

素材包 Markdown 条目要求：

- 每条以 `- ` 开头，包含 `priority: 核心/参考` 与 `source_type: 真实数据/用户投喂/AI推断`
- 真实数据必须带 `source` 或 `url`
- 核心素材必须有可检索关键词（`kw`）或原文 token，供成稿引用率校验

示例：

```markdown
- 事实：某模型推理成本下降 73%（priority: 核心；source_type: 真实数据；url: https://example.com）
```
