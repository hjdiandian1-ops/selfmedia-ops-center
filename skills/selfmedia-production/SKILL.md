---
name: selfmedia-production
description: 自媒体工业化内容生产｜用于从原始素材/逐字稿萃取《素材事实清单》，并自动生成符合公众号/小红书/短视频调性的高赞文案与分镜台本。
dependency:
  python:
    - jinja2>=3.0.0
license: MIT
---

# ✍️ 自媒体工业化内容生产 (selfmedia-production)

从结构化事实出发，执行多平台内容工业化高质量改写。

---

## 🎯 核心生产标准

1. **事实先行**：任何生产任务必须先生成或提供《素材事实清单》，严禁大模型凭空虚构未经证实的数据。
2. **三平台精准适配**：
   - **小红书**：前3秒视觉冲突 + emoji 视觉锚点 + 强互动行动钩子 + 3:4 组图分页设计。
   - **公众号**：深度叙事起伏 + 引用金句卡片 + 逻辑闭环结论。
   - **短视频**：120s 黄金节奏 + 景别与 B-roll 视效指示 + 删前保后口播台词。

---

## 🛠️ CLI 命令行用法

```bash
# 从原始文案提取事实清单
python3 -m selfmedia.production.extract --input draft.txt

# 生成小红书图文文案
python3 -m selfmedia.production.xhs --material facts.md

# 生成短视频分镜脚本
python3 -m selfmedia.production.video --material facts.md
```
