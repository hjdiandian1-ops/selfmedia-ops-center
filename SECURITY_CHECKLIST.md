# 发布前安全审查清单（SECURITY_CHECKLIST）

每次发布（release / push main）前逐项执行并勾选；任何一项不通过不得发布。

## 1. 秘密与脱敏
- [ ] `gitleaks dir . --redact`：0 高险命中（或在报告中注明排除项）
- [ ] `detect-secrets scan .`：无真实凭据
- [ ] `rg` 兜底：`sk-` / `AKIA` / `AIza` / `ghp_` / `Bearer` / `BEGIN PRIVATE KEY` / 手机号 / 邮箱 / 内网 IP 零命中
- [ ] 本地绝对路径零命中：`rg '/Users/|/home/[a-z]+/|C:\\Users\\'`（防报告/日志把本机目录结构写入仓库）
- [ ] `git ls-files` 不含 jobs/outputs/materials/data/nas-n8n 真实文件

## 2. 依赖漏洞
- [ ] `python3 scripts/security/osv_audit.py -r requirements.lock`：0 已知漏洞
- [ ] 依赖版本锁定在 requirements.lock，不出现裸 `>=`

## 3. 代码漏洞（SAST）
- [ ] `bandit -r scripts/ -q`：无 HIGH（或逐条说明）
- [ ] `semgrep --config auto scripts/ webapp/`：WARNING 逐条 triage
- [ ] 五类攻击面复核：命令注入 / SSRF / 路径遍历 / 恶意文件 / XSS

## 4. 供应链与许可证
- [ ] `pip-licenses` 输出无禁止再分发的 copyleft（LGPL 依赖可接受）
- [ ] 第三方 skill 不打包，仅链接 + 原 LICENSE 注明

## 5. 仓库与 CI
- [ ] GitHub 已开启：secret scanning + push protection、Dependabot、CodeQL
- [ ] main 分支保护：PR + 检查 + 签名提交
- [ ] `security.yml` 四道闸门（gitleaks/bandit/pip-audit/semgrep）在 PR 上运行
- [ ] Release 使用 immutable tag + attestation

## 6. 隐私与合规
- [ ] 个人真实数据（账号统计/草稿/范文）零入库
- [ ] README 明确「本地单机、禁止公网直连」边界
- [ ] 付费包授权文件含「个人非转让」条款
