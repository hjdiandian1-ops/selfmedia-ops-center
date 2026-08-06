#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频快剪合成器（路径 B：卡片 + TTS + ffmpeg，零成本本机合成）
================================================================
把 120s 分镜脚本变成 MP4：每镜 = 一张卡片图 + macOS say TTS 配音 + 花字，
按音频时长驱动镜头长度，最后拼接并烧录全片字幕。

用法：
    python3 scripts/video_compose.py shots.json -o out.mp4
    python3 scripts/video_compose.py shots.json -o out.mp4 --voice Tingting --rate 160 --no-subtitle

shots.json 格式：
{
  "title": "视频标题",
  "shots": [
    {"image": "outputs/.../xhs-01.png", "vo": "口播台词（TTS 友好写法）",
     "caption": "花字（短）", "pad": 0.5}
  ]
}

依赖：macOS say/afinfo（系统自带）+ imageio-ffmpeg（venv 静态 ffmpeg，含 libx264/aac/drawtext/subtitles）
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

VENV_FF = "/Users/xiaowuliao/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
FONT = "/System/Library/Fonts/PingFang.ttc"
W, H = 1080, 1440


def find_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    if os.path.exists(VENV_FF):
        return VENV_FF
    env = os.environ.get("FFMPEG")
    if env and os.path.exists(env):
        return env
    sys.exit("❌ 找不到 ffmpeg：请 pip install imageio-ffmpeg 或设置 FFMPEG 环境变量")


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"命令失败: {' '.join(cmd[:3])}...\n{r.stderr[-800:]}")
    return r


def tts_say(text, voice, rate, out_aiff):
    run(["say", "-v", voice, "-r", str(rate), "-o", out_aiff, text])


def audio_duration(path):
    r = run(["afinfo", path])
    m = re.search(r"estimated duration:\s*([\d.]+)\s*sec", r.stdout)
    if not m:
        raise RuntimeError(f"无法读取音频时长: {path}")
    return float(m.group(1))


_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️\ufe0f]")


def dt_escape(text):
    """drawtext 文本转义（filter_complex_script 文件模式，无需 shell 转义）"""
    text = _EMOJI.sub("", text).strip()
    for ch, rep in [("\\", "\\\\"), (":", "\\:"), ("%", "\\%"), ("'", "\\'"), ("[", "\\["), ("]", "\\]"), (",", "\\,")]:
        text = text.replace(ch, rep)
    return text


def wrap_vo(text, width=16):
    """把口播长句按标点边界切成 ≤width 字的短行（SRT 多行字幕，避免 libass 不自动换行）"""
    import re as _re
    parts = _re.split(r"([，。：；！？、])", text)
    segs = []
    for i in range(0, len(parts) - 1, 2):
        segs.append(parts[i] + parts[i + 1])
    if parts and parts[-1]:
        segs.append(parts[-1])
    lines, cur = [], ""
    for seg in segs:
        if len(cur) + len(seg) > width and cur:
            lines.append(cur)
            cur = seg
        else:
            cur += seg
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def srt_time(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser(description="视频快剪合成器")
    ap.add_argument("shots_json")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--voice", default="Tingting")
    ap.add_argument("--rate", type=int, default=160, help="say 语速（默认 160）")
    ap.add_argument("--no-subtitle", action="store_true", help="不烧录底部口播字幕")
    args = ap.parse_args()

    ff = find_ffmpeg()
    with open(args.shots_json, "r", encoding="utf-8") as f:
        spec = json.load(f)
    shots = spec["shots"]
    if not shots:
        sys.exit("❌ shots 为空")

    root = os.path.dirname(os.path.abspath(args.shots_json))
    work = tempfile.mkdtemp(prefix="video_compose_")
    print(f"🎬 开始合成《{spec.get('title', '未命名')}》：{len(shots)} 个镜头（工作目录 {work}）")

    segments, timeline = [], []
    cursor = 0.0
    for i, shot in enumerate(shots, 1):
        img = shot["image"] if os.path.isabs(shot["image"]) else os.path.join(root, shot["image"])
        if not os.path.exists(img):
            sys.exit(f"❌ 镜头 {i} 图片不存在: {img}")
        aiff = os.path.join(work, f"vo_{i:02d}.aiff")
        tts_say(shot["vo"], args.voice, args.rate, aiff)
        dur = audio_duration(aiff) + float(shot.get("pad", 0.5))
        dur = max(dur, 2.5)

        caption = dt_escape(shot.get("caption", ""))
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=white")
        if caption:
            vf += (f",drawtext=fontfile='{FONT}':text='{caption}':fontsize=52:fontcolor=white:"
                   f"box=1:boxcolor=black@0.55:boxborderw=22:x=(w-text_w)/2:y=100")

        seg = os.path.join(work, f"seg_{i:02d}.mp4")
        filter_file = os.path.join(work, f"vf_{i:02d}.txt")
        with open(filter_file, "w", encoding="utf-8") as f:
            f.write(vf)
        run([ff, "-y", "-loop", "1", "-framerate", "30", "-i", img, "-i", aiff,
             "-filter_complex_script", filter_file,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "128k", "-t", f"{dur:.2f}", "-r", "30", seg])
        segments.append(seg)
        timeline.append((cursor, cursor + dur, shot["vo"]))
        cursor += dur
        print(f"  ✅ 镜头 {i}: {dur:.1f}s（{os.path.basename(img)} + TTS）")

    # 拼接
    concat_list = os.path.join(work, "concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for s in segments:
            f.write(f"file '{s}'\n")
    concat_out = os.path.join(work, "concat.mp4")
    run([ff, "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", concat_out])

    final = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(final), exist_ok=True)

    if args.no_subtitle:
        run([ff, "-y", "-i", concat_out, "-c", "copy", final])
    else:
        # 生成 SRT 并烧录（失败则降级为无字幕版）
        srt = os.path.join(work, "final.srt")
        with open(srt, "w", encoding="utf-8") as f:
            idx = 0
            for st, et, vo in timeline:
                lines = wrap_vo(vo).split("\n")
                # 每 2 行一组拆成子条目，按字数比例分配时长（TTS 语速均匀，近似口型同步）
                chunks = ["\n".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
                weights = [max(len(c.replace("\n", "")), 1) for c in chunks]
                total_w = sum(weights)
                cur = st
                for ci, (c, wgt) in enumerate(zip(chunks, weights)):
                    idx += 1
                    nxt = et if ci == len(chunks) - 1 else cur + (et - st) * wgt / total_w
                    f.write(f"{idx}\n{srt_time(cur)} --> {srt_time(nxt)}\n{c}\n\n")
                    cur = nxt
        try:
            # 显式 PlayRes=视频分辨率，避免 libass 默认 384x288 脚本坐标被放大 5 倍
            sub_vf = (f"subtitles='{srt}':force_style='PlayResX={W},PlayResY={H},"
                      f"FontName=PingFang SC,FontSize=38,"
                      f"PrimaryColour=&HFFFFFF,OutlineColour=&H90000000,BorderStyle=3,"
                      f"BackColour=&H90000000,Alignment=2,MarginV=70'")
            sub_filter = os.path.join(work, "subvf.txt")
            with open(sub_filter, "w", encoding="utf-8") as f:
                f.write(sub_vf)
            run([ff, "-y", "-i", concat_out, "-filter_complex_script", sub_filter,
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                 "-c:a", "copy", final])
        except RuntimeError as e:
            print(f"⚠️ 字幕烧录失败，降级为无字幕版：{e}")
            run([ff, "-y", "-i", concat_out, "-c", "copy", final])

    size_mb = os.path.getsize(final) / 1024 / 1024
    print(f"\n🎉 合成完成：{final}")
    print(f"   总时长 {cursor:.1f}s ｜ {len(shots)} 镜头 ｜ {size_mb:.1f} MB ｜ {W}x{H}")


if __name__ == "__main__":
    main()
