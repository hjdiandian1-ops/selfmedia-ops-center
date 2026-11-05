#!/usr/bin/env python3
"""
自媒体发布 Agent - AI 生图 API 统一连接器
路径：scripts/generate_ai_image.py
支持硅基流动 (SiliconFlow / FLUX)、OpenAI DALL-E 3、火山引擎 (即梦) 等生图 API，生成 3:4 小红书/公众号插画与封面图。
"""

import os
import sys
import json
import argparse
import urllib.request

# 环境变量 API KEY
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

def generate_siliconflow_flux(prompt, output_path, aspect_ratio="3:4"):
    """ 使用 硅基流动 API (FLUX.1-schnell / FLUX.1-dev) 生成图片 """
    if not SILICONFLOW_API_KEY:
        print("⚠️ 未设置 SILICONFLOW_API_KEY 环境变量，请先配置！")
        return False
        
    url = "https://api.siliconflow.cn/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 解析宽高比例 3:4 -> 768x1024
    width, height = 768, 1024
    if aspect_ratio == "1:1":
        width, height = 1024, 1024
    elif aspect_ratio == "16:9":
        width, height = 1024, 576
        
    payload = {
        "model": "black-forest-labs/FLUX.1-schnell",
        "prompt": prompt,
        "image_size": f"{width}x{height}",
        "num_inference_steps": 20
    }
    
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
    
    try:
        print(f"🎨 正在请求 硅基流动 FLUX API 生成 3:4 图片: {prompt[:40]}...")
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            image_url = result["images"][0]["url"]
            
            # 下载并保存图片
            urllib.request.urlretrieve(image_url, output_path)
            print(f"✅ AI 封面成功保存至: {output_path}")
            return True
    except Exception as e:
        print(f"❌ 生图请求失败: {e}")
        return False

def render_fallback_cover_png(prompt: str, output_path: str, aspect_ratio: str = "3:4") -> bool:
    """当未配置云端生图 API Key 时，使用 PIL 渲染高分辨率 3:4 极客社媒视觉封面卡 (封面.png)。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import re

        width, height = 900, 1200
        if aspect_ratio == "1:1":
            width, height = 1024, 1024
        elif aspect_ratio == "16:9":
            width, height = 1280, 720

        img = Image.new("RGB", (width, height), (250, 250, 248))
        draw = ImageDraw.Draw(img)

        # 顶部克莱因蓝装饰条与卡片外框
        draw.rectangle([0, 0, width, 24], fill=(0, 47, 167))
        draw.rounded_rectangle([36, 56, width - 36, height - 56], radius=24, fill=(255, 255, 255), outline=(226, 232, 240), width=3)
        draw.rounded_rectangle([68, 92, 340, 144], radius=10, fill=(0, 47, 167))

        font_paths = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        ]
        def _load_font(size: int):
            for fp in font_paths:
                if os.path.exists(fp):
                    try:
                        return ImageFont.truetype(fp, size)
                    except Exception:
                        continue
            return ImageFont.load_default()

        f_tag = _load_font(24)
        f_title = _load_font(52)
        f_sub = _load_font(28)
        f_body = _load_font(24)
        f_foot = _load_font(20)

        draw.text((88, 104), "小吴聊AI · 实测干货", fill=(255, 255, 255), font=f_tag)

        # 提取主标题或核心文本
        m_top = re.search(r"【主标题】([^\n]+)", prompt) or re.search(r"【主题】([^\n]+)", prompt)
        clean_p = re.sub(r"\s+", " ", prompt).strip()
        headline = (m_top.group(1).strip() if m_top else clean_p[:28]).strip()
        if len(headline) < 6:
            headline = clean_p[:28]

        # 自动分行绘制大标题
        y_cursor = 185
        line_len = 13 if width <= 950 else 18
        for i in range(0, min(len(headline), line_len * 3), line_len):
            seg = headline[i : i + line_len]
            draw.text((68, y_cursor), seg, fill=(15, 23, 42), font=f_title)
            y_cursor += 70

        # 核心数据高亮面板
        panel_top = max(y_cursor + 30, 420)
        panel_bottom = min(height - 150, panel_top + 480)
        draw.rounded_rectangle([68, panel_top, width - 68, panel_bottom], radius=18, fill=(241, 245, 249), outline=(203, 213, 225), width=2)
        draw.text((96, panel_top + 28), "📊 核心实测指标与工程拆解", fill=(0, 47, 167), font=f_sub)

        summary_lines = [ln.strip() for ln in prompt.splitlines() if ln.strip()][:8]
        sy = panel_top + 82
        wrap_w = 26 if width <= 950 else 36
        for sln in summary_lines:
            for j in range(0, len(sln), wrap_w):
                if sy > panel_bottom - 44:
                    break
                draw.text((96, sy), sln[j : j + wrap_w], fill=(51, 65, 85), font=f_body)
                sy += 38

        # 底部品牌签名栏
        draw.line([(68, height - 120), (width - 68, height - 120)], fill=(226, 232, 240), width=2)
        draw.text((68, height - 96), "全网同名 · 小吴聊AI | 9大Agent工业级内容流水线", fill=(100, 116, 139), font=f_foot)

        img.save(output_path, format="PNG")
        print(f"✅ 已生成本地高分辨率视觉封面卡: {output_path} ({width}x{height})")
        return True
    except Exception as e:
        print(f"⚠️ 本地封面渲染降级异常: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="自媒体 Agent 专属 AI 生图工具")
    parser.add_argument("--prompt", required=True, help="画面描述/Prompt (包含风格、构图、光影)")
    parser.add_argument("--output", default="output_images/ai_cover.png", help="输出图片保存路径")
    parser.add_argument("--ratio", default="3:4", help="图片比例 (3:4, 1:1, 16:9)")
    
    args = parser.parse_args()
    
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    
    # 默认使用 SiliconFlow FLUX 服务，未配置 Key 时自动降级生成本地高清 3:4 视觉封面 PNG
    success = generate_siliconflow_flux(args.prompt, args.output, args.ratio)
    if not success:
        render_fallback_cover_png(args.prompt, args.output, args.ratio)

if __name__ == "__main__":
    main()

