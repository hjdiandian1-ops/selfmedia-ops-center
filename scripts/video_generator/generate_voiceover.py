#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import os
import json
import subprocess
import edge_tts
import imageio_ffmpeg

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "outputs", "video_assets")
os.makedirs(OUTPUT_DIR, exist_ok=True)
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

SCENES = [
    {
        "id": "scene_01",
        "title": "痛点暴击",
        "badge": "自媒体人现状",
        "text": "一个人做自媒体，最崩溃的是什么？每天找选题找两小时，写完排版一小时，发出去还因为 AI 味太重直接被平台限流。",
        "highlights": ["选题焦虑 2 小时", "纯人工排版抓狂", "AI腔过重被限流"],
    },
    {
        "id": "scene_02",
        "title": "中台登场",
        "badge": "自媒体运营工厂 2.0",
        "text": "所以，我做了这款「自媒体运营工厂 2.0」——把你从一个疲惫的码字民工，直接升级成拥有 9 个 AI 员工的内容总监！",
        "highlights": ["一人即是一座内容工厂", "9 个 AI 员工全流程协同", "开箱即用 · 闭环交付"],
    },
    {
        "id": "scene_03",
        "title": "全网雷达",
        "badge": "1.5秒零配置全网采集",
        "text": "早上开机，全网 8 大热点源 1.5 秒秒级采集完成！日更池、周更池自动基于热度与时效加权打分，爆款选题直接喂到嘴边。",
        "highlights": ["8 大国内源 1.5s 极速直连", "独创日/周双池加权算法", "爆款潜力智能打分"],
    },
    {
        "id": "scene_04",
        "title": "流水线生产",
        "badge": "9-Agent 流水线协同",
        "text": "点击采纳，流水线瞬间启动：资深采编搜集素材，主编撰写硬核长文，美术总监自动注入交互式可视化组件，三分钟产出全套图文！",
        "highlights": ["资深采编 + 主编 + 美术总监", "自动插入交互数据可视化组件", "小红书/公众号/短视频一键全出"],
    },
    {
        "id": "scene_05",
        "title": "硬核质检",
        "badge": "4 道可计算机器质检",
        "text": "觉得 AI 写的内容没灵魂？我们内置了 22 条去 AI 味可计算规则与合规审查，消灭所有空话套话，机器质检通过才准归档！",
        "highlights": ["22 条硬核去 AI 味检测规则", "4 道机器可计算质检链", "零违规 · 零 AI 假大空"],
    },
    {
        "id": "scene_06",
        "title": "高颜值多平台",
        "badge": "8套高定质感主题",
        "text": "还有 8 套高定质感主题自由换肤。公众号一键复制免排版，小红书卡片式视觉，短视频 120 秒分镜脚本一应俱全。",
        "highlights": ["爱马仕橙 / 香奈儿 / 赛博朋克等", "公众号一键复制（完美兼容微信）", "小红书高清卡片 + 视频分镜"],
    },
    {
        "id": "scene_07",
        "title": "立即体验",
        "badge": "开源核心 · 零依赖开箱",
        "text": "免费版核心完全开源，零依赖开箱即用。无论 Mac 还是 Windows，一键拉起你专属的内容中台。赶紧去体验吧！",
        "highlights": ["核心功能永久 MIT 开源", "Mac / Windows 跨平台支持", "GitHub 搜索: selfmedia-ops-center"],
    },
]

def get_audio_duration(file_path):
    cmd = [FFMPEG_EXE, "-i", file_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
    if m:
        hours, mins, secs = m.groups()
        return int(hours) * 3600 + int(mins) * 60 + float(secs)
    return 0.0

async def generate_all():
    voice = "zh-CN-YunxiNeural"
    rate = "+12%"
    
    meta = []
    total_duration = 0.0
    for s in SCENES:
        sid = s["id"]
        txt = s["text"]
        mp3_path = os.path.join(OUTPUT_DIR, f"{sid}.mp3")
        srt_path = os.path.join(OUTPUT_DIR, f"{sid}.srt")
        print(f"🎙️ 生成配音 [{sid}]: {txt[:20]}...")
        communicate = edge_tts.Communicate(txt, voice, rate=rate)
        submaker = edge_tts.SubMaker()
        
        with open(mp3_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    submaker.feed(chunk)
                    
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(submaker.get_srt())
            
        dur = get_audio_duration(mp3_path)
        total_duration += dur
        print(f"   ⏱️ 时长: {dur:.2f} 秒")
        
        meta.append({
            "id": sid,
            "title": s["title"],
            "badge": s["badge"],
            "text": txt,
            "highlights": s["highlights"],
            "mp3": mp3_path,
            "srt": srt_path,
            "duration": dur,
        })
        
    meta_path = os.path.join(OUTPUT_DIR, "scenes_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"total_duration": total_duration, "scenes": meta}, f, ensure_ascii=False, indent=2)
        
    print(f"\n🎉 全部 7 幕配音与字幕已就绪！总时长: {total_duration:.2f} 秒")
    print(f"📄 元数据已保存: {meta_path}")
    return meta

if __name__ == "__main__":
    asyncio.run(generate_all())
