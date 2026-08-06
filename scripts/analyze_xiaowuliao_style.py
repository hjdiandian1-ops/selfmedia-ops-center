#!/usr/bin/env python3
import os
import re
from collections import Counter

ARTICLES_DIR = "/Users/xiaowuliao/Downloads/公众号文章抓取/小吴聊"

def analyze_articles():
    files = [f for f in os.listdir(ARTICLES_DIR) if f.endswith(".md")]
    print(f"📚 找到 {len(files)} 篇小吴聊公众号历史发文:")
    
    titles = []
    openings = []
    
    for f_name in files:
        file_path = os.path.join(ARTICLES_DIR, f_name)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        if lines:
            titles.append(lines[0])
            
        # 寻找真实正文开始
        for line in lines[5:]:
            if not line.startswith("<") and not line.startswith("="):
                openings.append(line[:100])
                break
            
    print("\n📌 典型发文标题模式 (Title Patterns):")
    for t in titles[:10]:
        print(f"  - {t}")
        
    print("\n🔥 开篇 Hook 与接地气口吻 (Openings):")
    for op in openings[:6]:
        print(f"  > \"{op}...\"")

if __name__ == "__main__":
    analyze_articles()
