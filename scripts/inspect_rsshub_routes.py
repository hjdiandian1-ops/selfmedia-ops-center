#!/usr/bin/env python3
"""
深入测试 NAS 端 RSSHub 各热门路由真实抓取数据
路径：scripts/inspect_rsshub_routes.py
"""

import urllib.request
import json
import re

NAS_IP = "192.168.50.229"

ROUTES = [
    {"name": "GitHub Trending (全语言热门开源)", "url": f"http://{NAS_IP}:1200/github/trending/daily/any/zh"},
    {"name": "V2EX 极客与技术热帖", "url": f"http://{NAS_IP}:1200/v2ex/topics/latest"},
    {"name": "少数派 (SSPAI) 效率与工具", "url": f"http://{NAS_IP}:1200/sspai/matrix"},
    {"name": "36氪 科技/快讯", "url": f"http://{NAS_IP}:1200/36kr/newsflashes"},
]

def test_route(route):
    print(f"\n==================================================")
    print(f"📡 抓取测试: 【{route['name']}】")
    print(f"🔗 URL: {route['url']}")
    print(f"==================================================")
    
    req = urllib.request.Request(route["url"], headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read().decode("utf-8")
            
            raw_items = re.findall(r'<item>(.*?)</item>', xml_data, re.DOTALL)
            print(f"✅ 抓取到 {len(raw_items)} 条原始记录，以下展示前 3 条:")
            
            for idx, item_str in enumerate(raw_items[:3], 1):
                title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item_str)
                if not title_match:
                    title_match = re.search(r'<title>(.*?)</title>', item_str)
                    
                link_match = re.search(r'<link>(.*?)</link>', item_str)
                if not link_match:
                    link_match = re.search(r'<guid.*?>(.*?)</guid>', item_str)
                    
                desc_match = re.search(r'<description><!\[CDATA\[(.*?)\]\]></description>', item_str, re.DOTALL)
                if not desc_match:
                    desc_match = re.search(r'<description>(.*?)</description>', item_str, re.DOTALL)
                    
                title = title_match.group(1).strip() if title_match else "无标题"
                link = link_match.group(1).strip() if link_match else "无链接"
                raw_desc = desc_match.group(1).strip() if desc_match else ""
                clean_desc = re.sub(r'<[^>]+>', '', raw_desc).strip()
                
                print(f"\n  [{idx}] 标题: {title}")
                print(f"      链接: {link}")
                print(f"      正文: {clean_desc[:120]}...")
    except Exception as e:
        print(f"❌ 抓取失败: {e}")

if __name__ == "__main__":
    for r in ROUTES:
        test_route(r)
