# -*- coding: utf-8 -*-
"""选题推荐器单测（纯函数，不读热点雷达文件、不触网）。"""
import suggest_topics as ST


def test_normalize_title():
    assert ST.normalize_title("1. 用 AI 搞副业（[链接](http://x)）") == "用 AI 搞副业"


def test_score_item_keywords():
    assert ST.score_item("AI Agent 如何帮程序员副业赚钱") > 0
    assert ST.score_item("今天吃了一碗面") == 0


def test_suggest_view():
    # DECONSTRUCT 优先级高于 DIALOGUE：含「融资/钱」等词的先归硬核拆解
    assert ST.suggest_view("这家公司融资了 1000 万") == "【硬核拆解】"
    assert ST.suggest_view("如何用 AI 省钱提升效率") == "【硬核拆解】"
    # 仅含公司/创业等对话词、无钱相关词 → 商业对话
    assert ST.suggest_view("这家公司创始人分享创业经验") == "【商业对话】"
    assert ST.suggest_view("一个有趣的观察") == "【商业观察】"


def test_suggest_formulas_fallback():
    assert ST.suggest_formulas("一个平淡的标题") == ["身份代入"]
    assert "数字冲击" in ST.suggest_formulas("3 个方法提升效率")
