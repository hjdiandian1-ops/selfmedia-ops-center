---
name: selfmedia-video
description: 短视频物理渲染与成片引擎｜用于通过 HTML 确定性逐帧渲染 1080x1920 动效 B-roll、FFmpeg 动态侧链避让混音（-18dB 压低 BGM）与成片 MP4 一键合成。
dependency:
  python:
    - playwright>=1.30.0
    - imageio-ffmpeg>=0.4.0
    - jinja2>=3.0.0
license: MIT
---

# 🎬 短视频物理渲染与成片引擎 (selfmedia-video)

真正输出可播放的商业级高清 MP4 短视频成片。

---

## 🎯 核心技术突破

1. **HTML ➔ MP4 确定性 B-roll 渲染**：彻底告别 PPT 录屏，通过无头浏览器时间轴精准控制动效进度与高质感光晕，直接导出 1080x1920 竖屏 MP4。
2. **Sidechain Audio Ducking 侧链混音**：人声响起时背景音自动压低 -18dB，人声间歇平滑回升，告别手工调音轨。
3. **成片一键装配**：自动对齐音视频时间轴并合成发布级 MP4。

---

## 🛠️ CLI 命令行用法

```bash
# 渲染单个 B-roll 动效片段
python3 -m selfmedia.video.broll --scene scene.json --duration 5 --out ./outputs/broll.mp4

# 人声与背景音乐智能混音
python3 -m selfmedia.video.mix --voice voice.mp3 --bgm music.mp3 --out ./outputs/mixed.mp3

# 成片合成
python3 -m selfmedia.video.compose --video broll.mp4 --audio mixed.mp3 --out ./outputs/final.mp4
```
