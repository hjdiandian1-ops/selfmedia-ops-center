#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宣发视频场景视觉渲染器 (1080x1920 竖屏 9:16)
============================================================
生成高质感、高对比度、带毛玻璃特效和动态光效的场景帧。
"""
import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH = 1080
HEIGHT = 1920
FPS = 30

FONT_MAIN_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"
if not os.path.exists(FONT_MAIN_PATH):
    FONT_MAIN_PATH = "/System/Library/Fonts/STHeiti Light.ttc"
if not os.path.exists(FONT_MAIN_PATH):
    FONT_MAIN_PATH = "/Library/Fonts/Arial Unicode.ttf"

def get_font(size, bold=False):
    try:
        index = 1 if bold and FONT_MAIN_PATH.endswith(".ttc") else 0
        return ImageFont.truetype(FONT_MAIN_PATH, size, index=index)
    except Exception:
        return ImageFont.load_default()

def draw_rounded_rect(draw, bbox, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=width)

def create_gradient_bg(width, height, c_top, c_bottom, glow_center=None, glow_color=None, glow_radius=400):
    """生成科技感垂直渐变背景与发光光晕"""
    base = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    top_r, top_g, top_b = c_top
    bot_r, bot_g, bot_b = c_bottom
    
    # 垂直渐变数组
    y = np.linspace(0, 1, height)[:, None]
    r = (top_r * (1 - y) + bot_r * y).astype(np.uint8)
    g = (top_g * (1 - y) + bot_g * y).astype(np.uint8)
    b = (top_b * (1 - y) + bot_b * y).astype(np.uint8)
    a = np.full((height, width), 255, dtype=np.uint8)
    
    rgb = np.dstack([np.repeat(r, width, axis=1),
                     np.repeat(g, width, axis=1),
                     np.repeat(b, width, axis=1),
                     a])
    img = Image.fromarray(rgb, "RGBA")
    
    if glow_center and glow_color:
        gx, gy = glow_center
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        for rad in range(glow_radius, 0, -30):
            alpha = int(glow_color[3] * (1 - rad / glow_radius) * 0.4)
            gdraw.ellipse([gx - rad, gy - rad, gx + rad, gy + rad], fill=(glow_color[0], glow_color[1], glow_color[2], alpha))
        glow = glow.filter(ImageFilter.GaussianBlur(40))
        img = Image.alpha_composite(img, glow)
        
    return img

def render_scene_frame(scene_idx, t, duration, scene_meta):
    """
    根据场景索引与当前时间 t (秒) 渲染 1080x1920 高清视频帧
    """
    progress = min(1.0, max(0.0, t / max(0.1, duration)))
    
    # 通用容器画板
    if scene_idx == 0: # 痛点暴击
        bg = create_gradient_bg(WIDTH, HEIGHT, (15, 8, 12), (5, 2, 4),
                                glow_center=(540, 800), glow_color=(239, 68, 68, 120), glow_radius=500)
    elif scene_idx == 1: # 中台登场
        bg = create_gradient_bg(WIDTH, HEIGHT, (10, 16, 35), (4, 6, 15),
                                glow_center=(540, 750), glow_color=(59, 130, 246, 140), glow_radius=550)
    elif scene_idx == 2: # 全网雷达
        bg = create_gradient_bg(WIDTH, HEIGHT, (8, 28, 22), (3, 12, 10),
                                glow_center=(540, 780), glow_color=(16, 185, 129, 130), glow_radius=500)
    elif scene_idx == 3: # 9-Agent流水线
        bg = create_gradient_bg(WIDTH, HEIGHT, (20, 12, 38), (8, 5, 18),
                                glow_center=(540, 820), glow_color=(139, 92, 246, 140), glow_radius=520)
    elif scene_idx == 4: # 22条去AI味质检
        bg = create_gradient_bg(WIDTH, HEIGHT, (6, 24, 30), (2, 10, 14),
                                glow_center=(540, 760), glow_color=(6, 182, 212, 140), glow_radius=500)
    elif scene_idx == 5: # 8套质感主题
        bg = create_gradient_bg(WIDTH, HEIGHT, (28, 18, 10), (10, 6, 4),
                                glow_center=(540, 800), glow_color=(245, 158, 11, 130), glow_radius=500)
    else: # 立即体验 CTA
        bg = create_gradient_bg(WIDTH, HEIGHT, (12, 16, 32), (5, 6, 16),
                                glow_center=(540, 780), glow_color=(99, 102, 241, 150), glow_radius=550)
        
    draw = ImageDraw.Draw(bg)
    
    # 1. 顶部 Badge
    badge_txt = scene_meta.get("badge", "自媒体运营工厂 2.0")
    badge_font = get_font(34, bold=True)
    badge_w = draw.textlength(badge_txt, font=badge_font)
    bx1 = (WIDTH - badge_w) / 2 - 32
    by1 = 160
    bx2 = bx1 + badge_w + 64
    by2 = by1 + 64
    draw_rounded_rect(draw, (bx1, by1, bx2, by2), 32, fill=(255, 255, 255, 25), outline=(255, 255, 255, 60), width=2)
    draw.text((bx1 + 32, by1 + 12), badge_txt, font=badge_font, fill=(255, 255, 255, 240))
    
    # 2. 顶部主标题
    title_txt = scene_meta.get("title", "")
    title_font = get_font(68, bold=True)
    tw = draw.textlength(title_txt, font=title_font)
    draw.text(((WIDTH - tw) / 2, 260), title_txt, font=title_font, fill=(255, 255, 255, 255))
    
    # 3. 中部核心视觉卡片区 (Y: 380 - 1380)
    card_x1, card_y1, card_x2, card_y2 = 70, 380, WIDTH - 70, 1420
    
    # 场景特定动画与卡片绘制
    if scene_idx == 0:
        _render_scene_01(draw, progress, card_x1, card_y1, card_x2, card_y2)
    elif scene_idx == 1:
        _render_scene_02(draw, progress, card_x1, card_y1, card_x2, card_y2)
    elif scene_idx == 2:
        _render_scene_03(draw, progress, card_x1, card_y1, card_x2, card_y2)
    elif scene_idx == 3:
        _render_scene_04(draw, progress, card_x1, card_y1, card_x2, card_y2)
    elif scene_idx == 4:
        _render_scene_05(draw, progress, card_x1, card_y1, card_x2, card_y2)
    elif scene_idx == 5:
        _render_scene_06(draw, progress, card_x1, card_y1, card_x2, card_y2)
    else:
        _render_scene_07(draw, progress, card_x1, card_y1, card_x2, card_y2)
        
    # 4. 底部字幕与进度条区域 (Y: 1480 - 1800)
    _render_subtitles_and_progress(draw, scene_meta.get("text", ""), progress)
    
    return bg.convert("RGB")


# ============================================================
# 各幕具体视觉卡片渲染
# ============================================================

def _render_scene_01(draw, p, x1, y1, x2, y2):
    """第 1 幕：自媒体人 3 大深夜痛点"""
    items = [
        ("🛑 选题枯竭", "翻遍各大热搜依然不知道写什么，每天选题耗费 2 小时"),
        ("🛑 排版地狱", "文案、配图、格式反复调，深夜还在为排版抓狂"),
        ("🛑 AI 腔被限流", "通篇「首先、由此可见、不仅如此」，发出去 0 播放 0 曝光"),
    ]
    card_h = 280
    gap = 40
    start_y = y1 + 50
    
    for i, (head, desc) in enumerate(items):
        cy1 = start_y + i * (card_h + gap)
        cy2 = cy1 + card_h
        
        # 卡片入场动效
        card_p = min(1.0, max(0.0, (p - i * 0.15) / 0.4))
        alpha_box = int(25 + card_p * 20)
        
        draw_rounded_rect(draw, (x1, cy1, x2, cy2), 24, fill=(239, 68, 68, alpha_box), outline=(239, 68, 68, 120), width=2)
        
        # 标头
        draw.text((x1 + 45, cy1 + 40), head, font=get_font(52, bold=True), fill=(254, 202, 202, 255))
        # 描述 (自动换行)
        draw.text((x1 + 45, cy1 + 120), desc[:18], font=get_font(36), fill=(229, 231, 235, 230))
        if len(desc) > 18:
            draw.text((x1 + 45, cy1 + 175), desc[18:], font=get_font(36), fill=(229, 231, 235, 230))


def _render_scene_02(draw, p, x1, y1, x2, y2):
    """第 2 幕：自媒体中台登场与 9 Agent 协同架构"""
    # 主卡片
    draw_rounded_rect(draw, (x1, y1, x2, y2), 28, fill=(30, 41, 59, 140), outline=(59, 130, 246, 150), width=2)
    
    # 核心枢纽
    hub_cx, hub_cy = (x1 + x2) // 2, y1 + 200
    draw_rounded_rect(draw, (hub_cx - 300, hub_cy - 70, hub_cx + 300, hub_cy + 70), 35,
                      fill=(37, 99, 235, 200), outline=(147, 197, 253, 255), width=3)
    draw.text((hub_cx - 240, hub_cy - 30), "⚡ 自媒体运营工厂 2.0", font=get_font(44, bold=True), fill=(255, 255, 255, 255))
    
    # 9 大 Agent 矩阵
    agents = [
        ("🔍 资深采编", "全网热点聚合"), ("📊 选题分析", "双池加权打分"), ("✍️ 长文主编", "金字塔结构"),
        ("🎨 美术总监", "交互数据组件"), ("🧼 质检总监", "22条去AI味"), ("🛡️ 合规审核", "敏感词初筛"),
        ("📱 小红书主编", "高颜值卡片"), ("📰 公众号主编", "一键排版直推"), ("🎬 视频导演", "120s黄金分镜"),
    ]
    
    start_y = y1 + 350
    grid_w = (x2 - x1 - 60) // 3
    grid_h = 175
    
    for i, (name, role) in enumerate(agents):
        row = i // 3
        col = i % 3
        gx1 = x1 + 20 + col * (grid_w + 10)
        gy1 = start_y + row * (grid_h + 15)
        gx2 = gx1 + grid_w
        gy2 = gy1 + grid_h
        
        # 呼吸发光动效
        glow_pulse = math.sin(p * 6 + i) * 20 + 40
        draw_rounded_rect(draw, (gx1, gy1, gx2, gy2), 18, fill=(15, 23, 42, int(glow_pulse + 100)),
                          outline=(59, 130, 246, int(glow_pulse + 120)), width=2)
        draw.text((gx1 + 20, gy1 + 30), name, font=get_font(34, bold=True), fill=(255, 255, 255, 240))
        draw.text((gx1 + 20, gy1 + 95), role, font=get_font(28), fill=(148, 163, 184, 220))


def _render_scene_03(draw, p, x1, y1, x2, y2):
    """第 3 幕：1.5 秒全网热点雷达 + 双池加权评分"""
    draw_rounded_rect(draw, (x1, y1, x2, y2), 28, fill=(6, 78, 59, 80), outline=(16, 185, 129, 140), width=2)
    
    # 顶部数据指标
    draw.text((x1 + 45, y1 + 50), "🌐 8 大国内直连源 · 1.5 秒秒级采集", font=get_font(42, bold=True), fill=(52, 211, 153, 255))
    
    # 实时热搜榜卡片
    sources = [
        ("微博热搜", "防灾减灾救灾 总书记强调三个到位", "790万热搜", (239, 68, 68)),
        ("B站热门", "【硬核】自媒体全自动流水线实操", "120万播放", (59, 130, 246)),
        ("少数派", "一人超级个体的生产力飞轮指南", "矩阵精选", (245, 158, 11)),
        ("掘金热榜", "AI 编程 Agent 架构实战全解析", "4.8万阅读", (16, 185, 129)),
    ]
    
    sy = y1 + 130
    for s_name, title, heat, color in sources:
        draw_rounded_rect(draw, (x1 + 35, sy, x2 - 35, sy + 130), 16, fill=(15, 23, 42, 160), outline=(255, 255, 255, 40), width=1)
        draw_rounded_rect(draw, (x1 + 55, sy + 35, x1 + 215, sy + 95), 10, fill=color, outline=None)
        draw.text((x1 + 75, sy + 45), s_name, font=get_font(28, bold=True), fill=(255, 255, 255, 255))
        draw.text((x1 + 235, sy + 45), title[:14] + "...", font=get_font(32), fill=(255, 255, 255, 230))
        draw.text((x2 - 220, sy + 48), heat, font=get_font(26), fill=(156, 163, 175, 200))
        sy += 150
        
    # 底部加权打分展示
    draw_rounded_rect(draw, (x1 + 35, y2 - 250, x2 - 35, y2 - 40), 20, fill=(4, 120, 87, 120), outline=(52, 211, 153, 200), width=2)
    draw.text((x1 + 65, y2 - 210), "🏆 AI 选题加权打分池 (时效×1.2 + 热度×1.2)", font=get_font(36, bold=True), fill=(255, 255, 255, 255))
    draw.text((x1 + 65, y2 - 130), "日更池 Top 1：AI 编程 Agent 工业化落地", font=get_font(34), fill=(209, 250, 229, 240))
    draw.text((x2 - 200, y2 - 135), "95.4 分", font=get_font(40, bold=True), fill=(52, 211, 153, 255))


def _render_scene_04(draw, p, x1, y1, x2, y2):
    """第 4 幕：9 Agent 流水线全自动生产与交互可视化"""
    draw_rounded_rect(draw, (x1, y1, x2, y2), 28, fill=(46, 16, 101, 80), outline=(139, 92, 246, 150), width=2)
    
    # 顶部流程
    draw.text((x1 + 45, y1 + 50), "⚡ 一键采纳 · 3 分钟全流水线闭环", font=get_font(42, bold=True), fill=(196, 181, 253, 255))
    
    steps = [
        ("1. 资料与素材搜集", "资深采编 Agent 聚合全网论据与硬核事实", (59, 130, 246)),
        ("2. 长文主编起草", "严格遵循金字塔结构，拒绝大话套话", (139, 92, 246)),
        ("3. 自动注入可视化组件", "美术总监生成红白/深色交互式对比图表", (236, 72, 153)),
        ("4. 三端成品同步出炉", "微信排版 + 小红书卡片 + 短视频分镜", (16, 185, 129)),
    ]
    
    sy = y1 + 140
    for s_title, s_desc, color in steps:
        draw_rounded_rect(draw, (x1 + 35, sy, x2 - 35, sy + 175), 18, fill=(15, 23, 42, 180), outline=color, width=2)
        draw.text((x1 + 65, sy + 30), s_title, font=get_font(38, bold=True), fill=color)
        draw.text((x1 + 65, sy + 95), s_desc, font=get_font(30), fill=(229, 231, 235, 220))
        sy += 205


def _render_scene_05(draw, p, x1, y1, x2, y2):
    """第 5 幕：22 条去 AI 味规则与 4 道硬核质检"""
    draw_rounded_rect(draw, (x1, y1, x2, y2), 28, fill=(8, 51, 68, 90), outline=(6, 182, 212, 160), width=2)
    
    draw.text((x1 + 45, y1 + 50), "🧼 22 条去 AI 味机器可计算检测", font=get_font(42, bold=True), fill=(103, 232, 249, 255))
    
    rules = [
        ("🛑 二元对立壳", "不是…而是… / 不是工具问题而是认知问题", "自动消解"),
        ("🛑 助词三连套", "值得注意的是 / 本质上来说 / 毋庸置疑", "严格剔除"),
        ("🛑 假大空总结", "由此可见 / 综上所述 / 让我们拭目以待", "重写替换"),
        ("🛑 结构三拍子", "首先、其次、最后三段式僵硬排比", "流式重构"),
    ]
    
    sy = y1 + 140
    for r_name, r_example, r_action in rules:
        draw_rounded_rect(draw, (x1 + 35, sy, x2 - 35, sy + 155), 16, fill=(15, 23, 42, 180), outline=(6, 182, 212, 90), width=1)
        draw.text((x1 + 60, sy + 30), r_name, font=get_font(34, bold=True), fill=(248, 113, 113, 255))
        draw.text((x1 + 60, sy + 85), r_example, font=get_font(28), fill=(203, 213, 225, 220))
        draw_rounded_rect(draw, (x2 - 190, sy + 45, x2 - 60, sy + 105), 12, fill=(6, 182, 212, 180))
        draw.text((x2 - 175, sy + 58), r_action, font=get_font(26, bold=True), fill=(255, 255, 255, 255))
        sy += 180
        
    # 底部认证大标
    draw_rounded_rect(draw, (x1 + 35, y2 - 170, x2 - 35, y2 - 40), 18, fill=(16, 185, 129, 140), outline=(52, 211, 153, 255), width=2)
    draw.text((x1 + 180, y2 - 130), "✅ 4 重机器质检 PASS · 合规认证", font=get_font(38, bold=True), fill=(255, 255, 255, 255))


def _render_scene_06(draw, p, x1, y1, x2, y2):
    """第 6 幕：8 套高定质感换肤 + 多平台一键导出"""
    draw_rounded_rect(draw, (x1, y1, x2, y2), 28, fill=(69, 26, 3, 80), outline=(245, 158, 11, 150), width=2)
    
    draw.text((x1 + 45, y1 + 50), "🎨 8 套高定质感主题 · 一键换肤", font=get_font(42, bold=True), fill=(251, 191, 36, 255))
    
    themes = [
        ("爱马仕橙 (Hermes)", "奢华活力 · 质感飞升", (234, 88, 12)),
        ("香奈儿黑金 (Chanel)", "极简克制 · 高端商务", (217, 119, 6)),
        ("赛博朋克 (Cyberpunk)", "霓虹光暴 · 极客代码", (168, 85, 247)),
        ("和风藤紫 (Fuji)", "雅致静谧 · 深度阅读", (99, 102, 241)),
    ]
    
    sy = y1 + 135
    for t_name, t_sub, color in themes:
        draw_rounded_rect(draw, (x1 + 35, sy, x2 - 35, sy + 130), 16, fill=(24, 24, 27, 190), outline=color, width=2)
        draw_rounded_rect(draw, (x1 + 55, sy + 30, x1 + 125, sy + 100), 12, fill=color)
        draw.text((x1 + 150, sy + 30), t_name, font=get_font(34, bold=True), fill=(255, 255, 255, 255))
        draw.text((x1 + 150, sy + 80), t_sub, font=get_font(28), fill=(212, 212, 216, 220))
        sy += 150
        
    # 三平台导出展示
    draw_rounded_rect(draw, (x1 + 35, y2 - 250, x2 - 35, y2 - 40), 20, fill=(39, 39, 42, 190), outline=(251, 191, 36, 180), width=2)
    draw.text((x1 + 65, y2 - 210), "📱 微信公众号排版一键复制 · 完美粘贴", font=get_font(32, bold=True), fill=(255, 255, 255, 240))
    draw.text((x1 + 65, y2 - 145), "✨ 小红书高清图文卡片 + 视频分镜直出", font=get_font(32, bold=True), fill=(255, 255, 255, 240))


def _render_scene_07(draw, p, x1, y1, x2, y2):
    """第 7 幕：开源核心 + 跨平台一键体验 CTA"""
    draw_rounded_rect(draw, (x1, y1, x2, y2), 28, fill=(30, 27, 75, 90), outline=(99, 102, 241, 160), width=2)
    
    draw.text((x1 + 45, y1 + 50), "🚀 核心完全开源 · 零依赖开箱即用", font=get_font(42, bold=True), fill=(165, 180, 252, 255))
    
    # 命令行卡片
    draw_rounded_rect(draw, (x1 + 35, y1 + 140, x2 - 35, y1 + 400), 20, fill=(15, 23, 42, 230), outline=(99, 102, 241, 120), width=2)
    draw.text((x1 + 65, y1 + 175), "$ git clone https://github.com/.../selfmedia-ops", font=get_font(30), fill=(148, 163, 184, 240))
    draw.text((x1 + 65, y1 + 235), "$ ./start.sh", font=get_font(34, bold=True), fill=(52, 211, 153, 255))
    draw.text((x1 + 65, y1 + 310), "✨ 自动拉起 http://127.0.0.1:8787 工作台", font=get_font(32), fill=(199, 210, 254, 255))
    
    # GitHub 仓库卡片
    draw_rounded_rect(draw, (x1 + 35, y1 + 440, x2 - 35, y1 + 680), 20, fill=(24, 24, 27, 210), outline=(255, 255, 255, 60), width=2)
    draw.text((x1 + 65, y1 + 480), "⭐ GitHub 开源项目", font=get_font(34, bold=True), fill=(255, 255, 255, 255))
    draw.text((x1 + 65, y1 + 545), "hjdiandian1-ops/selfmedia-ops-center", font=get_font(34, bold=True), fill=(96, 165, 250, 255))
    draw.text((x1 + 65, y1 + 610), "跨平台兼容 Mac 与 Windows", font=get_font(30), fill=(156, 163, 175, 220))
    
    # 底部高亮按钮
    btn_p = (math.sin(p * 8) + 1) * 0.5
    btn_fill = (99, 102, 241, int(200 + btn_p * 55))
    draw_rounded_rect(draw, (x1 + 35, y2 - 230, x2 - 35, y2 - 60), 28, fill=btn_fill, outline=(255, 255, 255, 200), width=3)
    draw.text((x1 + 160, y2 - 165), "🔥 立即体验你的专属自媒体中台", font=get_font(40, bold=True), fill=(255, 255, 255, 255))


def _render_subtitles_and_progress(draw, text, p):
    """底部字幕容器与播放进度条"""
    sub_y1 = 1520
    sub_y2 = 1780
    sub_x1 = 60
    sub_x2 = WIDTH - 60
    
    # 字幕卡片
    draw_rounded_rect(draw, (sub_x1, sub_y1, sub_x2, sub_y2), 24, fill=(0, 0, 0, 180), outline=(255, 255, 255, 40), width=2)
    
    # 字幕文字 (自动断行排版)
    sub_font = get_font(44, bold=True)
    chars_per_line = 18
    lines = [text[i:i + chars_per_line] for i in range(0, len(text), chars_per_line)]
    
    line_y = sub_y1 + 45 if len(lines) == 1 else sub_y1 + 35
    for line in lines[:3]:
        lw = draw.textlength(line, font=sub_font)
        draw.text(((WIDTH - lw) / 2, line_y), line, font=sub_font, fill=(255, 235, 59, 255))
        line_y += 65
        
    # 最底部视频进度条
    prog_y = 1860
    draw_rounded_rect(draw, (80, prog_y, WIDTH - 80, prog_y + 12), 6, fill=(255, 255, 255, 40))
    current_w = int((WIDTH - 160) * p)
    if current_w > 0:
        draw_rounded_rect(draw, (80, prog_y, 80 + current_w, prog_y + 12), 6, fill=(59, 130, 246, 255))


if __name__ == "__main__":
    test_frame = render_scene_frame(0, 2.0, 10.0, {
        "title": "痛点暴击",
        "badge": "自媒体人现状",
        "text": "一个人做自媒体，最崩溃的是什么？每天找选题找两小时，写完排版一小时，发出去还因为 AI 味太重直接被平台限流。"
    })
    test_out = "/Users/xiaowuliao/Projects/自媒体发布agent/outputs/video_assets/test_frame_01.png"
    test_frame.save(test_out)
    print(f"✅ 测试帧已保存: {test_out}")
