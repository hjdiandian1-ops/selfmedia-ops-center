# Contributing

感谢你愿意参与「自媒体运营工厂开源核心」。

## 我们接受什么

- 去 AI 味规则新增/阈值修正（附测试与真实样例）；
- 合规词库扩充（附平台规则依据）；
- 授权体系的安全加固与文档；
- 安全扫描脚本与 CI 改进。

## 我们暂不接受

- 包含真实账号数据、发布内容或第三方 skill 的 PR；
- 与付费 Pro 包功能重合的完整生产流程实现（请通过商业渠道合作）。

## 流程

1. Fork 并新建分支 `feat/xxx` 或 `fix/xxx`；
2. 为改动补测试（`pytest tests/`）；
3. 提交前本地跑：`bandit -r scripts` + `pip-audit -r requirements.lock` + `gitleaks dir .`；
4. 提交 PR，main 分支需要至少 1 个 review + CI 全绿。

## 行为准则

友善、就事论事；不发布未验证的“爆款方法论”；尊重第三方 skill 版权。
