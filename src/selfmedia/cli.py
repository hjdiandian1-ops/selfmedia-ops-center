# -*- coding: utf-8 -*-
"""
SelfMedia Operations Factory Unified CLI (自媒体运营工厂统一命令行入口)
====================================================================
支持：
  selfmedia radar [gzh|search|transcribe]
  selfmedia produce [facts|xhs|video]
  selfmedia check [materials|ai-flavor|compliance|harsh]
  selfmedia render [xhs|diagram]
  selfmedia install [cursor|claude|codex|all]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .radar import fetch_gzh_explosive_articles, search_cross_platform, process_url_transcript
from .production import extract_material_facts, generate_xiaohongshu_post, generate_video_script
from .quality import validate_materials_contract, check_ai_flavor, check_compliance, evaluate_harsh_critic
from .visual import render_xhs_slide_deck, render_html_to_image, generate_pipeline_diagram_html


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="selfmedia",
        description="自媒体运营工厂 · 工业级 Agent Skills 命令行工具套件",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="子命令")

    # 1. Radar
    radar_parser = subparsers.add_parser("radar", help="📡 爆款情报探测与转录")
    radar_sub = radar_parser.add_subparsers(dest="action")

    gzh_cmd = radar_sub.add_parser("gzh", help="公众号爆款探测")
    gzh_cmd.add_argument("keyword", nargs="?", default="AI编程", help="赛道关键词")
    gzh_cmd.add_argument("--limit", type=int, default=10, help="最多返回数量")

    search_cmd = radar_sub.add_parser("search", help="跨平台社媒搜索")
    search_cmd.add_argument("keyword", nargs="?", default="AI工具", help="搜索关键词")

    tl1_cmd = radar_sub.add_parser("tl1", help="推楼1号 (TL1.com) X中文区热点雷达与AI脉搏")
    tl1_cmd.add_argument("--limit", type=int, default=10, help="最多返回数量")

    trans_cmd = radar_sub.add_parser("transcribe", help="音视频链接转录")
    trans_cmd.add_argument("url", help="音视频链接 (YT/B站/播客/抖/红)")
    trans_cmd.add_argument("--out", default="./outputs/transcripts", help="输出目录")


    # 2. Produce
    prod_parser = subparsers.add_parser("produce", help="✍️ 工业化内容生产")
    prod_sub = prod_parser.add_subparsers(dest="action")

    xhs_cmd = prod_sub.add_parser("xhs", help="生成小红书爆款图文文案")
    xhs_cmd.add_argument("--topic", default="自媒体工业化全自动工厂", help="选题名称")

    video_cmd = prod_sub.add_parser("video", help="生成短视频 120s 黄金分镜台本")
    video_cmd.add_argument("--topic", default="自媒体工业化全自动工厂", help="选题名称")

    # 3. Quality Check
    check_parser = subparsers.add_parser("check", help="🛡️ 四重质检门禁审核")
    check_parser.add_argument("file", help="待质检的 Markdown 或文本文件")

    # 4. Install Skills
    inst_parser = subparsers.add_parser("install", help="🚀 一键安装/软链到 Cursor / Claude / Codex Skills 目录")
    inst_parser.add_argument("--target", choices=["cursor", "claude", "codex", "all"], default="all", help="目标 IDE")

    return parser


def handle_install(target: str):
    home = Path.home()
    root_skills = Path(__file__).parent.parent.parent / "skills"
    
    target_dirs = []
    if target in ("cursor", "all"):
        target_dirs.append(home / ".cursor" / "skills")
    if target in ("claude", "all"):
        target_dirs.append(home / ".claude" / "skills")
    if target in ("codex", "all"):
        target_dirs.append(home / ".codex" / "skills")
    target_dirs.append(home / ".agents" / "skills")

    print(f"🚀 开始将自媒体技能套件安装至目标环境 ({target})...")
    installed_count = 0
    for target_base in target_dirs:
        target_base.mkdir(parents=True, exist_ok=True)
        for skill_dir in root_skills.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                dst = target_base / skill_dir.name
                if dst.exists() or dst.is_symlink():
                    try:
                        if dst.is_symlink():
                            dst.unlink()
                        elif dst.is_dir():
                            import shutil
                            shutil.rmtree(dst)
                    except Exception:
                        pass
                try:
                    dst.symlink_to(skill_dir.resolve(), target_is_directory=True)
                    print(f"  ✅ 已软链: {skill_dir.name} ➔ {dst}")
                    installed_count += 1
                except Exception as e:
                    print(f"  ⚠️ 安装 {skill_dir.name} 失败: {e}")

    print(f"\n🎉 技能套件安装完成！共成功挂载 {installed_count} 处路径。可在 Cursor / Claude Code / Codex 中直接用自然语言唤醒！")


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        return

    if args.subcommand == "radar":
        if args.action == "gzh":
            res = fetch_gzh_explosive_articles(args.keyword, max_items=args.limit)
            print(f"📡 微信公众号爆款探测（关键词: {args.keyword}，共 {res['count']} 篇）：")
            for idx, item in enumerate(res["items"], 1):
                print(f"  [{idx}] 【{item['category']}】{item['title']}")
                print(f"      公众号: {item['account_name']} | 阅读: {item['reads']} | 点赞: {item['likes']} | 分数: {item['data_score']}")
                print(f"      链接: {item['url']}")
        elif args.action == "search":
            res = search_cross_platform(args.keyword)
            for p, items in res["results"].items():
                print(f"\n📌 【{p}】找到 {len(items)} 条内容：")
                for it in items:
                    print(f"  - {it['title']} ({it.get('author', '')}) -> {it.get('url', '')}")
        elif args.action == "tl1":
            from .radar import fetch_tl1_hotspots
            res = fetch_tl1_hotspots(max_items=args.limit)
            print(f"🔥 推楼1号 (https://tl1.com/) X中文区热点雷达（共 {res['count']} 条）：\n")
            for idx, item in enumerate(res["items"], 1):
                print(f"  [{idx}] 【{item['source']}】{item['title']}")
                print(f"      热度: {item['heat']} | 作者: {item['author']} | 链接: {item['url']}")
                if item.get("summary"):
                    print(f"      摘要: {item['summary']}")
        elif args.action == "transcribe":
            res = process_url_transcript(args.url, output_dir=args.out)
            print(f"✅ 转录完成！产物路径：{res['md_path']}")


    elif args.subcommand == "produce":
        if args.action == "xhs":
            res = generate_xiaohongshu_post("素材内容", custom_title=args.topic)
            print(f"📝 小红书爆款文案生成成功（四重质检通过: {res['qa']['all_passed']}）：\n")
            print(res["content"])
        elif args.action == "video":
            res = generate_video_script("素材内容")
            print(f"🎬 短视频分镜台本生成成功（四重质检通过: {res['qa']['all_passed']}）：\n")
            print(res["script"])

    elif args.subcommand == "check":
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ 文件不存在: {args.file}")
            return
        text = file_path.read_text(encoding="utf-8")
        ai = check_ai_flavor(text)
        comp = check_compliance(text)
        critic = evaluate_harsh_critic("待审核文案", text)
        print(f"🛡️ 四重质检审核报告 ({args.file}):")
        print(f"  - 去AI味人味得分: {ai['score']} 分 ({ai['verdict']})")
        print(f"  - 合规敏感词审核: {comp['verdict']}")
        print(f"  - Harsh Critic 读者评审得分: {critic['total_score']} 分 ({critic['verdict']})")

    elif args.subcommand == "install":
        handle_install(args.target)


if __name__ == "__main__":
    main()
