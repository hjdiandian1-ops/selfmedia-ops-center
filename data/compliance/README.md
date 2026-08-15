# 内容合规词库（可外挂）

`scripts/compliance_check.py` 内置初版规则；本目录可放每行一个关键词/正则的 txt 词库，脚本自动加载：

- `ad.txt`：广告法绝对化用语（全平台）
- `xhs.txt`：小红书专属红线词
- `douyin.txt`：抖音专属红线词
- `gzh.txt`：公众号专属红线词

格式：每行一个词，`#` 开头为注释。可把 GitHub 开源违禁词库整理后直接放入。

高风险项（high）直接 REJECTED 禁止发布；中风险（medium）需人工复核；warn 为建议项。
