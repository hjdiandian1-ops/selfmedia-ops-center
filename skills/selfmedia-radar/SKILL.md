---
name: selfmedia-radar
description: 自媒体爆款情报与多源转录雷达｜用于公众号低粉爆款文章查询、小红书与B站垂类热门笔记搜索、以及 YouTube/小宇宙/B站/抖音/小红书音视频链接一键提取逐字稿与字幕。
dependency:
  python:
    - requests>=2.28.0
    - yt-dlp>=2024.0.0
    - imageio-ffmpeg>=0.4.0
license: MIT
---

# 📡 自媒体爆款情报与多源转录雷达 (selfmedia-radar)

用于全域内容创作者的「实时爆款探测」与「外部音视频转录」技能。

---

## 🎯 核心能力

1. **公众号低粉爆款探测**：按赛道/关键词全网实时扫描低粉丝高阅读量（黑马爆发）、10w+阅读、原创飙升榜文章。
2. **小红书/B站全域垂类搜索**：获取赛道高赞笔记与热门视频，分析前3秒钩子与用户高频痛点。
3. **跨平台链接音视频提取与转录**：输入 YouTube、小宇宙播客、B站、抖音、小红书链接，自动提取音频并转录为带时间戳的 Markdown 逐字稿与 SRT 字幕。

---

## 🛠️ CLI 命令行用法

### 1. 公众号爆款文章查询
```bash
# 搜索指定赛道的公众号爆款（默认展示低粉高赞、10w+榜单）
python3 -m selfmedia.radar.gzh_trends "AI编程" 10

# 搜索全站热门
python3 -m selfmedia.radar.gzh_trends "" 10
```

### 2. 跨平台社媒搜索（小红书 / B站 / 抖音）
```bash
# 跨平台聚合搜索
python3 -m selfmedia.radar.xhs_search "独立开发"
```

### 3. 任意链接一键转录为逐字稿与字幕
```bash
# 解析音视频链接，产物落盘至 outputs/transcripts/
python3 -m selfmedia.radar.transcript "https://www.bilibili.com/video/BV1kS8H6VERt"
```

---

## 🤖 Agent 调用场景与话术范式

| 用户输入 | Agent 路由与行为 |
|---|---|
| 「帮我看看最近公众号关于【AI智能体】有什么爆款文章」 | 调用 `fetch_gzh_explosive_articles("AI智能体", max_items=10)`，提取低粉爆款标题、阅读量、点赞量与核心摘要呈现给用户。 |
| 「帮我搜一下小红书上大家怎么讨论【Cursor编程】的」 | 调用 `search_cross_platform("Cursor编程")`，提取高赞笔记与热门视频。 |
| 「把这个视频/播客链接提取一下文字稿：https://...」 | 调用 `process_url_transcript("<URL>")`，输出带时间戳 Markdown 逐字稿并总结其爆款结构。 |

---

## 📊 输出规范

- **公众号爆款数据**：包含 `category`（低粉爆款/10w+）、`title`、`account_name`、`reads`、`likes`、`data_score` 及原文链接。
- **逐字稿与字幕**：落盘生成 `outputs/transcripts/{标题}_transcript.md` 与 `outputs/transcripts/{标题}_subtitles.srt`。
