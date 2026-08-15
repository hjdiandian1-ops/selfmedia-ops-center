# -*- coding: utf-8 -*-
"""选题推荐器单测（纯函数，不读热点雷达文件、不触网）。"""
from datetime import datetime, timedelta, timezone

import suggest_topics as ST


def test_normalize_title():
    assert ST.normalize_title("1. 用 AI 搞副业（[链接](http://x)）") == "用 AI 搞副业"


def test_score_item_keywords():
    assert ST.score_item("AI Agent 如何帮程序员副业赚钱") > 0
    assert ST.score_item("今天吃了一碗面") == 0


def test_match_niches():
    prefs = {"platforms": {"小红书": ["科技数码", "美食"]}}
    niches = {"小红书": {"科技数码": ["AI", "科技"], "美食": ["美食", "食谱"]}}
    assert ST.match_niches("AI 大模型发布", "", prefs, niches) == ["小红书·科技数码"]
    assert ST.match_niches("周末探店美食攻略", "", prefs, niches) == ["小红书·美食"]
    assert ST.match_niches("今天天气不错", "", prefs, niches) == []
    assert ST.match_niches("今天天气不错", "", {}, niches) == []


def test_suggest_view():
    # DECONSTRUCT 优先级高于 DIALOGUE：含「融资/钱」等词的先归硬核拆解
    assert ST.suggest_view("这家公司融资了 1000 万") == "【硬核拆解】"
    assert ST.suggest_view("如何用 AI 省钱提升效率") == "【硬核拆解】"
    # 仅含公司/创业等对话词、无钱相关词 → 商业对话
    assert ST.suggest_view("这家公司创始人分享创业经验") == "【商业对话】"
    assert ST.suggest_view("一个有趣的观察") == "【商业观察】"


def test_suggest_formulas_fallback():
    assert ST.suggest_formulas("一个平淡的标题") == ["反常识"]
    assert "数字冲击" in ST.suggest_formulas("3 个方法提升效率")


def test_suggest_formula_detail():
    weak = ST.suggest_formula_detail("AI 智能体产品体验", ["反常识"])
    assert "备选" in weak and "#" in weak  # 弱信号给出主推+备选，不再是统一身份代入
    assert "#23" in ST.suggest_formula_detail("给打工人看的 AI 工具", ["身份代入"])
    assert "#27" in ST.suggest_formula_detail("3 个步骤提升效率", ["数字冲击"])
    assert "#26" in ST.suggest_formula_detail("3 个效率小窍门", ["数字冲击"])
    assert "#12" in ST.suggest_formula_detail("为什么 AI 同事能替代打工人", ["悬念好奇"])


def test_fresh_info():
    now = datetime.now(timezone.utc)
    fresh = ST.fresh_info((now - timedelta(hours=3)).strftime("%a, %d %b %Y %H:%M:%S +0000"))
    assert fresh["label"] == "12 小时内"
    assert abs(fresh["score"] - 5.75) < 0.1  # 连续分 ≈ 6 − 3/12

    mid = ST.fresh_info((now - timedelta(hours=30)).isoformat())
    assert mid["label"] == "2 天内"
    assert mid["score"] == 3.5  # 6 − 30/12

    day = ST.fresh_info((now - timedelta(hours=20)).isoformat())
    assert day["label"] == "24 小时内"
    assert day["score"] == 4.3  # 6 − 20/12

    three = ST.fresh_info((now - timedelta(hours=70)).isoformat())
    assert three["label"] == "3 天内"
    assert three["score"] == 0.2

    stale = ST.fresh_info((now - timedelta(days=5)).isoformat())
    assert stale["label"] == "5 天前"
    assert stale["score"] == 0.0
    assert stale["stale"] is True

    assert ST.fresh_info("")["label"] == "时效未知"


def test_fresh_info_tl1_hour_key():
    now = datetime.now(timezone.utc)
    hour_key = (now + timedelta(hours=8)).strftime("%Y%m%d%H")  # 北京时间
    fresh = ST.fresh_info(hour_key)
    assert fresh["score"] >= 5.9
    assert fresh["label"] == "12 小时内"


def test_parse_radar_with_publish_time(tmp_path):
    radar = tmp_path / "radar.md"
    radar.write_text(
        "## X热点\n\n"
        "1. 过时新闻（[链接](https://x.com/a)）（发布于 2026-08-01 10:00）（摘要 旧闻不采）｜ ⚠️ 海外源·需人工复核\n"
        "2. 新鲜新闻（[链接](https://x.com/b)）（发布于 2026-08-08 10:00）｜ ⚠️ 海外源·需人工复核\n",
        encoding="utf-8")
    rows = ST.parse_radar(str(radar))
    assert rows[0][4] == "2026-08-01 10:00"
    assert rows[1][4] == "2026-08-08 10:00"
    assert rows[0][6] == "旧闻不采"
    assert rows[1][6] == ""


def test_extract_heat():
    assert ST.extract_heat("谷歌Pixel 11系列发布（9）") == ("谷歌Pixel 11系列发布", "（9）", 9.0)
    assert ST.extract_heat("the traitors new blood（500+）")[2] == 500.0
    assert ST.extract_heat("某新闻（100.2万热度）")[2] == 1002000.0
    # 4 位数字是年份，不当作热度
    assert ST.extract_heat("年度报告（2026）")[2] is None
    assert ST.extract_heat("无热度标题")[2] is None


def test_score_dimensions():
    d = ST.score_dimensions("AI Agent 教程：如何对比三款大模型价格，附避坑清单")
    assert d["ip"] > 0
    assert d["search"] >= 3   # 教程/如何/对比/价格
    assert d["durable"] >= 1  # 教程/清单
    assert ST.score_dimensions("今天吃了一碗面") == {
        "ip": 0, "impact": 0, "search": 0, "durable": 0, "unique": 0}


def test_score_rows_heat_normalization_and_rank_fallback():
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    rows = [
        ("AI 大模型爆发（9）", "推楼1号小时热点", "", 1, "2026081223", 9.0, ""),
        ("AI 大模型爆发（3）", "推楼1号小时热点", "", 2, "2026081223", 3.0, ""),
        ("普通小热点", "少数派热门", "", 3, now, None, ""),
    ]
    scored = ST.score_rows(rows)
    by_rank = {it["rank"]: it for it in scored}
    assert by_rank[1]["heat_score"] == 10.0   # (11-1) + 1.0 微调，封顶 10
    assert abs(by_rank[2]["heat_score"] - 9.3) < 1e-9  # 9 + 3/9
    assert by_rank[3]["heat_score"] == 8.0    # 无热度：11-3
    assert by_rank[1]["score"] > by_rank[2]["score"]


def test_score_excludes_ip_from_total():
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    rows = [
        ("AI 智能体教程", "36氪快讯", "", 1, now, None, ""),
    ]
    it = ST.score_rows(rows)[0]
    assert "ip" not in it["score_breakdown"]
    assert it["score"] == sum(it["score_breakdown"].values())
    assert it["dims"]["ip"] == ST.MAX_DIM  # IP 保留在维度里作门槛/排序
    assert "daily_score" in it and "weekly_score" in it


def test_dedupe_cross_source_bonus():
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    rows = [
        ("AI 智能体教程", "36氪快讯", "", 1, now, None, ""),
        ("AI 智能体教程", "推楼1号小时热点", "", 2, now, None, ""),
    ]
    scored = ST.score_rows(rows)
    picks = ST.dedupe_and_rank(scored)
    assert len(picks) == 1
    assert picks[0]["source_count"] == 2
    assert picks[0]["score_breakdown"]["cross_source"] == ST.CROSS_SOURCE_BONUS
    assert picks[0]["score"] == sum(picks[0]["score_breakdown"].values())


def test_dedupe_noise_suffix():
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    rows = [
        ("xAI发布Grok Bot云端同事（AI资讯）", "hex2077·产品与功能更新", "", 1, now, None, ""),
        ("xAI推出Grok Bot 云端同事", "推楼1号小时热点", "", 2, now, None, ""),
    ]
    picks = ST.dedupe_and_rank(ST.score_rows(rows))
    assert len(picks) == 1
    assert picks[0]["source_count"] == 2


def test_summary_participates_in_text_dims():
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    rows = [
        ("英伟达发布闪电模型", "36氪快讯", "", 1, now, None, "性能炸裂，低延迟评测第一"),
    ]
    it = ST.score_rows(rows)[0]
    assert it["dims"]["search"] > 0    # 发布
    assert it["dims"]["durable"] > 0   # 模型/低延迟/评测
    assert it["dims"]["impact"] > 0    # 炸裂


def test_build_pools_gates():
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%a, %d %b %Y %H:%M:%S +0000")
    rows = [
        ("AI 模型最新发布", "36氪快讯", "", 1, now_str, None, ""),
        ("AI 旧闻教程", "36氪快讯", "", 2, (now - timedelta(hours=48)).isoformat(), None, ""),
        ("AI 过时新闻", "36氪快讯", "", 3, (now - timedelta(days=5)).isoformat(), None, ""),
    ]
    deduped = ST.dedupe_and_rank(ST.score_rows(rows))
    daily, weekly = ST.build_pools(deduped, daily_top=2, weekly_top=2)
    daily_titles = [it["title"] for it in daily]
    weekly_titles = [it["title"] for it in weekly]
    assert "AI 模型最新发布" in daily_titles
    assert "AI 旧闻教程" not in daily_titles   # 48h：时效 2.0 < 4
    assert all(it["heat_score"] >= ST.DAILY_HEAT_GATE for it in daily)
    assert "AI 旧闻教程" in weekly_titles      # 教程命中搜索信号
    assert "AI 过时新闻" not in weekly_titles  # 过时不进任何池
    assert len(daily) <= 2 and len(weekly) <= 2
