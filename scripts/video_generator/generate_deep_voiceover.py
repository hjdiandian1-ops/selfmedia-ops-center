#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import os
import json
import re
import subprocess
import edge_tts
import imageio_ffmpeg

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(ROOT, "outputs", "video_assets", "deep_walkthrough")
os.makedirs(OUTPUT_DIR, exist_ok=True)
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

SCENES = [
    {
        "id": "scene_00_hook",
        "title": "强力 Hook：痛点反差",
        "badge": "市面玩具 vs 落地中枢",
        "text": "作为一个每天都要更新的自媒体人，我之前最头疼的就是：找热点翻遍全网找两小时，写完排版又折腾一小时，发出去还因为 AI 味太重直接被平台限流。后来我用上了这个开源的自媒体运营工厂 2.0，直接把我的全套工作流搬到了本地。今天就以我的日常使用视角，手把手带大家看看它是怎么帮我每天 10 分钟搞定多平台生产的。",
    },
    {
        "id": "scene_01_onboard",
        "title": "首次打开与新手指引",
        "badge": "3 分钟新手指引",
        "text": "首次在浏览器打开工作台，中央会自动弹出一个 3 分钟新手指引。这里非常清晰地帮新手划出了 4 个核心步骤：先在设置里配好 AI 引擎，接着看今日推荐选题，然后一键采纳自动生产，最后在成品库直接取用发布。哪怕是纯小白，跟着这 4 步也能 3 分钟上手。了解之后，我们点击底部的‘我知道了，开始使用’，关闭引导，正式进入工作台。",
    },
    {
        "id": "scene_02_dashboard",
        "title": "概览大盘：全景掌控",
        "badge": "三端全景看板 & 诊断雷达",
        "text": "关掉引导后，我们看到的是工作台首页：概览大盘。这里实时聚合了公众号、小红书、短视频三端的核心运营数据与发布节奏。系统还会自动生成账号薄弱点诊断雷达，一眼看出你是选题欠缺热度、排版停留率低，还是完播率不足，数据驱动，不再盲目摸黑发文。",
    },
    {
        "id": "scene_03_topics",
        "title": "选题雷达：1.5秒全网捕获",
        "badge": "8 大国内源 & 双池加权打分",
        "text": "每天早上开工第一件事：点击左侧的选题模块。点一下‘采集热点’，只要 1.5 秒，微博热搜、B站热门、知乎、百度、少数派等 8 大主流热榜就全抓回来了，完全不需要翻墙或配置复杂的爬虫。往下看，系统已经用算法帮我们分好了‘日更池’和‘周更池’，每个选题都综合了时效、热度、质量和账号垂直度自动打分。比如今天这条 95 分的 AI 热门选题，爆款潜质最高，我就直接选它了。",
    },
    {
        "id": "scene_04_pipeline",
        "title": "采纳生产：9 Agent 全自动流水线",
        "badge": "一键采纳 & 9-Agent 协同",
        "text": "选好之后，直接点击‘采纳生产’。切换到流水线页面，你可以看到后台已经在全自动运转了：先是资深采编 Agent 帮我们搜集全网事实论据；接着长文主编开始按金字塔结构撰写深度正文；美术总监还会自动给文章插入好看的红白系交互数据图表；最后短视频导演生成 120 秒分镜。相当于有 9 个 AI 员工在后台帮你流水线作业，喝口咖啡的功夫，3 分钟全套图文就做好了。",
    },
    {
        "id": "scene_05_finished",
        "title": "成品验收：22 条去 AI 味机器质检",
        "badge": "4 道可计算质检 & 微信一键排版",
        "text": "内容做完后，我们来到成品库验收。很多人担心 AI 写出来的文章一股机器味，但这里内置了 22 条去 AI 味可计算规则，把不是…而是…、值得注意的是这种假大空套话全消解掉了，质检全绿才会放行。看看右边排版好的公众号文章，重点文字加粗、数据对比图表全都有。点击一键复制，直接粘贴到微信公众平台后台就能发，一秒都不用手动排版；左边还有小红书高清卡片和短视频脚本，真正做到拿来就能发。",
    },
    {
        "id": "scene_06_flywheel",
        "title": "运营复盘：爆款拆解与数据飞轮自进化",
        "badge": "对标拆解 & 经验反哺升级",
        "text": "平时想学习同行爆款，点开爆款跟踪，系统会抓取对标账号的万赞内容，AI 一键帮我们拆解它的引流钩子与文案骨架。发完内容拿到真实反馈后，来到数据飞轮。每次踩坑的教训和爆款经验都会沉淀在经验库里，点击一键反哺，这些经验就会自动写进 9 个 Agent 的 SOP 里，让整个平台越写越懂你的账号，越用越聪明。",
    },
    {
        "id": "scene_07_settings",
        "title": "设置中心全功能拆解",
        "badge": "7 项菜单逐一拆解 & 换肤",
        "text": "再来看我们的设置中心，左侧提供了完整的配置菜单：第一项个人资料，支持自定义你的头像与专属昵称；第二项外观主题，内置了爱马仕橙、香奈儿、赛博朋克等 8 套高定质感主题，点击就能一秒换肤，还能无级调节毛玻璃质感；第三项文风设置，你可以套用预设模板或使用 AI 向导，定制属于你自己的个人写作风格与专属 SOP；接着是 AI 引擎，填入 DeepSeek 或 OpenAI Key 即可唤醒 AI 生产力；如果要抓海外热点，在网络与代理填入代理并一键测试；配置好公众号还能实现草稿箱直推；最后在数据管理里，一键清理历史缓存为电脑瘦身。设置完成后点击返回即可。",
    },
    {
        "id": "scene_08_cta",
        "title": "开源开箱即用与行动号召",
        "badge": "核心完全开源 · 跨平台支持",
        "text": "最后说说怎么安装使用：这个项目的核心功能完全开源、零依赖，Mac 和 Windows 都能用。在 GitHub 搜索 selfmedia-ops-center 下载代码，运行一条启动脚本，浏览器就会自动打开这个工作台，直接就能上手操作。想要搭建属于自己的一人自媒体工厂的朋友，赶紧去 GitHub 体验并点个 Star 吧！",
    },
]

def get_audio_duration(file_path):
    cmd = [FFMPEG_EXE, "-i", file_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
    if m:
        hours, mins, secs = m.groups()
        return int(hours) * 3600 + int(mins) * 60 + float(secs)
    return 0.0

def format_ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    cs = int((s - int(s)) * 100)
    return f"{h:d}:{m:02d}:{int(s):02d}.{cs:02d}"

async def generate_deep_voiceover():
    voice = "zh-CN-YunxiNeural"
    rate = "+30%"  # 提速 30%，紧凑高燃、干脆利落！
    
    meta = []
    total_duration = 0.0
    
    for s in SCENES:
        sid = s["id"]
        txt = s["text"]
        mp3_path = os.path.join(OUTPUT_DIR, f"{sid}.mp3")
        print(f"🎙️ 生成高燃加速配音 ({rate}) [{sid}]: {txt[:25]}...")
        communicate = edge_tts.Communicate(txt, voice, rate=rate)
        await communicate.save(mp3_path)
        
        dur = get_audio_duration(mp3_path)
        total_duration += dur
        print(f"   ⏱️ 时长: {dur:.2f} 秒")
        
        meta.append({
            "id": sid,
            "title": s["title"],
            "badge": s["badge"],
            "text": txt,
            "mp3": mp3_path,
            "duration": dur,
        })
        
    meta_path = os.path.join(OUTPUT_DIR, "deep_scenes_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"total_duration": total_duration, "scenes": meta}, f, ensure_ascii=False, indent=2)
        
    # 生成纯净亮黄大字 + 黑色立体硬描边 ASS 字幕文件
    events = []
    current_time = 0.0
    
    for m in meta:
        text = m["text"]
        dur = m["duration"]
        
        clauses = [c.strip() for c in re.split(r"([，。？！——；、]+)", text) if c.strip()]
        merged = []
        i = 0
        while i < len(clauses):
            if i + 1 < len(clauses) and re.match(r"^[，。？！——；、]+$", clauses[i + 1]):
                merged.append(clauses[i] + clauses[i + 1])
                i += 2
            else:
                merged.append(clauses[i])
                i += 1
                
        total_chars = sum(len(c) for c in merged)
        t_start = current_time
        for c in merged:
            c_dur = max(0.75, dur * (len(c) / max(1, total_chars)))
            t_end = min(current_time + dur, t_start + c_dur)
            events.append(f"Dialogue: 0,{format_ass_time(t_start)},{format_ass_time(t_end)},Default,,0,0,0,,{c}")
            t_start = t_end
            
        current_time += dur
        
    # 爆款短视频标配字幕样式：
    # 纯净亮黄大字(PrimaryColour=&H0000E5FF) + 黑色立体粗描边(OutlineColour=&H00000000, Outline=3.5, Shadow=1)
    # 无底框遮挡(BorderStyle=1, BackColour=&H00000000)
    # 居中贴底 MarginV=55，左右安全边距 MarginL=70, MarginR=70
    ass_text = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Hiragino Sans GB,40,&H0000E5FF,&H00000000,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3.5,1,2,70,70,55,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(events)

    ass_file = os.path.join(OUTPUT_DIR, "deep_subtitles.ass")
    with open(ass_file, "w", encoding="utf-8") as f:
        f.write(ass_text)
        
    # 合并完整音轨
    full_audio = os.path.join(OUTPUT_DIR, "deep_full_voiceover.mp3")
    concat_txt = os.path.join(OUTPUT_DIR, "audio_concat.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for m in meta:
            f.write(f"file '{m['mp3']}'\n")
            
    subprocess.run([
        FFMPEG_EXE, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        full_audio
    ], check=True, stderr=subprocess.DEVNULL)
    
    print(f"\n🎉 全部 9 幕 +30% 高燃配音与 ASS 字幕已就绪！")
    print(f"⏱️ 视频总时长: {total_duration:.2f} 秒 ({total_duration/60:.2f} 分钟)")

if __name__ == "__main__":
    asyncio.run(generate_deep_voiceover())
