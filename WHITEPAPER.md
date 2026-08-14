# 自媒体运营工厂开源核心 · 技术白皮书

> 版本：v1.0 ｜ 配套仓库：selfmedia-ops-center（MIT）

## 1. 去 AI 味检查（22 条规则）

`scripts/ai_flavor_check.py` 把结构级 AI 腔转成可解释的机器检查，输出 `verdict = PASSED / WARN / REJECTED` 与逐条命中（规则、来源、次数、原文片段、修改建议）。

### 1.1 规则来源

| 来源 | 项目 | 许可 |
|---|---|---|
| [A] | zero-click/avoid-ai-writing-zh | MIT |
| [L] | liuliu-66-create/ll-humanizer-zh | 以仓库 LICENSE 为准 |
| [B] | B1lli/remove-ai-flavor-writing-skill | 以仓库 LICENSE 为准 |

### 1.2 判定阈值（与脚本一致）

| 等级 | 条件 |
|---|---|
| REJECTED（必须改） | 首先…其次…最后；对称式收束；报幕式过渡；贬低读者；二元对比壳 ≥3；本质断言 ≥3；助手路线标记 ≥2；虚假让步 ≥2；总结填充 ≥2；老师式自问自答 ≥3 |
| WARN（人工复核） | 本质断言 1-2；助手路线标记 1；二元对比壳 1-2；弱化框架 1-2；排比 ≥4；正文引号 ≥4；破折号 ≥2；反问开场；抒情过渡；替读者说话；空泛表扬；报告式分析 ≥3；无动机结尾问句 |

### 1.3 设计原则

1. **计数分级而非见词就杀**：真人也会偶尔说「本质上」「值得注意的是」，按次数分级避免误伤；
2. **跨平台合并计数**：同一规则在小红书/公众号/短视频各出现 1 次 = 3 次，按合并值判定；
3. **例外显式化**：真实人物引语、技术标识中的连字符属于引号/破折号例外，需人工确认；
4. **机器可数 + 人工判断**：展示型三拍、均匀段落形状机器不判定，列入人工复核清单。

## 2. 授权体系（Ed25519 签名 token + 设备绑定）

### 2.1 Token 结构

```
base64url(payload_json) + "." + base64url(ed25519_signature)

payload = {
  ver: 1,            # 版本
  uid: 订单号,        # 订单/用户标识
  tier: free|pro|owner,
  exp: YYYY-MM-DD,   # 到期日
  bind: 设备指纹,     # macOS IOPlatformUUID 哈希 / 通用设备哈希
  features: [...],   # pro 默认全量
  iat: 签发日
}
```

### 2.2 判定优先级（license_gate.check_feature）

1. 本地授权文件为 `owner` 模式 → 放行（卖家自用机）；
2. 无授权文件 → 免费功能放行（爆款拆解走 3 次/月额度），Pro 功能拒绝并输出升级链接；
3. 有 token → 验签 → 到期 → 设备指纹 → tier → features，全部通过才放行。

### 2.3 免费额度

- `~/.xiaowuliao-skills/quota.json` 本地计数，`month` 字段跨月自动重置；
- 免费用户 `viral_breakdown` 3 次/月；Pro token 用户无限（不走额度）；
- 本地计数可被删除重置——这是「防君子」设计的一部分，正式防滥用依赖 v2 在线授权。

### 2.4 安全边界（重要）

- 离线签名无法防专业破解：校验代码与文件都在用户手里，恶意用户可绕过；
- 设计目标：**防普通用户共享**（token 绑设备指纹，换机器验签失败），不构成 DRM；
- 企业级防滥用（吊销/限设备数/心跳）需要在 v2 部署授权服务器，代码已预留 `install.py --activate` 在线激活接口；
- 私钥只存在卖家本机 `~/.xiaowuliao-license/`（权限 600），公钥随付费包分发，仓库内只有公钥。

## 3. 安全工具覆盖

| 模块 | 防护 |
|---|---|
| security_utils.valid_job_id | job_id/theme 白名单正则，防路径穿越与命令参数注入 |
| security_utils.safe_http_url | SSRF：仅 http/https、禁 userinfo、禁内网/环回/链路本地/云元数据地址，域名解析后复核 |
| security_utils.safe_xlsx_zip | zip 炸弹：文件大小/条目数/单成员/总解压/压缩比五重上限 |
| check_public_repo.py | 发布前校验：禁止目录、凭据正则（API key/私钥/邮箱/手机号/内网 IP/**本机绝对路径**） |
| osv_audit.py | 依赖漏洞：按 requirements.lock 固定版本直查 OSV API |

## 4. CI 门禁

| Job | 工具 | 失败即阻止合并 |
|---|---|---|
| Secret Scan | gitleaks | ✅ |
| Dependency Audit | pip-audit | ✅ |
| Bandit | bandit -r scripts/ | ✅ |
| Semgrep | semgrep --config auto --error | ✅ |
| CodeQL | github/codeql-action（security-and-quality） | ✅ |
| Tests | pytest tests/ | ✅ |

## 5. FAQ

**Q：免费版和 Pro 版怎么切？**
免费功能（选题/排版/3 次拆解）无需授权；调用 Pro 功能时 `license_gate.py check` 未通过会输出升级链接。

**Q：换电脑怎么办？**
v1 联系卖家提供新设备指纹（`install.py --show-fingerprint`），卖家重签绑定 token；v2 提供自助换绑。

**Q：报告里的路径安全吗？**
安全。`ai_flavor_check.py` 会把 `output_dir` 相对化后再写入报告，且发布前检查强制扫描本机绝对路径零命中。

**Q：可以商用/二次分发吗？**
开源核心遵循 MIT；付费 Skill 包为「个人非转让授权」，商用与企业部署走企业版通道。
