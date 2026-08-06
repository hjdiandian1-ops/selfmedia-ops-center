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

def main():
    parser = argparse.ArgumentParser(description="自媒体 Agent 专属 AI 生图工具")
    parser.add_argument("--prompt", required=True, help="画面描述/Prompt (包含风格、构图、光影)")
    parser.add_argument("--output", default="output_images/ai_cover.png", help="输出图片保存路径")
    parser.add_argument("--ratio", default="3:4", help="图片比例 (3:4, 1:1, 16:9)")
    
    args = parser.parse_args()
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # 默认使用 SiliconFlow FLUX 服务
    success = generate_siliconflow_flux(args.prompt, args.output, args.ratio)
    if not success:
        print("💡 生图失败或提示缺少 API KEY。可选择手动指定图片，或降级使用 HTML 视觉卡片 (guizang-social-card-skill)。")

if __name__ == "__main__":
    main()
