#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Beav 封面提示词仓库爬虫脚本 (GetBeav Cover Prompts Crawler)
===========================================================
爬取 https://www.getbeav.com/templates 的全部封面提示词模板：
1. 抓取所有分页（基于 cursor 游标）；
2. 抓取模板详情页（完整AI提示词、画面比例、参考图、适用行业、标签、尺寸等）；
3. 将缩略图与高清原图本地化下载至 data/cover_templates/images/；
4. 输出结构化数据至 data/cover_templates/templates.json 与 README.md。
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

ROOT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUTPUT_DIR = os.path.join(ROOT_DIR, "data", "cover_templates")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
TEMPLATES_JSON = os.path.join(OUTPUT_DIR, "templates.json")
README_MD = os.path.join(OUTPUT_DIR, "README.md")

BASE_URL = "https://www.getbeav.com"
LIST_URL = "https://www.getbeav.com/templates"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


import subprocess


def fetch_html(url, retries=3):
    for i in range(retries):
        try:
            cmd = ["curl", "-s", "-L", "--max-time", "15", "-A", HEADERS["User-Agent"], url]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
            if res.returncode == 0 and res.stdout:
                return res.stdout.decode("utf-8", errors="replace")
        except Exception as e:
            time.sleep(1 + i)
            if i == retries - 1:
                print(f"[Error] Failed to fetch {url}: {e}")
                return None
    return None


def download_file(url, target_path, retries=3):
    if os.path.isfile(target_path) and os.path.getsize(target_path) > 1024:
        return True
    for i in range(retries):
        try:
            cmd = ["curl", "-s", "-L", "--max-time", "20", "-A", HEADERS["User-Agent"], "-o", target_path, url]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
            if res.returncode == 0 and os.path.isfile(target_path) and os.path.getsize(target_path) > 1024:
                return True
        except Exception as e:
            time.sleep(1 + i)
            if i == retries - 1:
                print(f"[Warn] Failed to download image {url} -> {target_path}: {e}")
                return False
    return False


def parse_listing_page(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []

    articles = soup.find_all("article")
    for art in articles:
        a_tag = art.find("a", href=True)
        if not a_tag:
            continue
        href = a_tag["href"]
        if not href.startswith("/templates/"):
            continue
        slug = href.replace("/templates/", "").strip("/")

        # Category
        cat_tag = art.find("p", class_=lambda c: c and "tracking-" in c)
        category = cat_tag.get_text().strip() if cat_tag else "其他"

        # Title
        h2 = art.find("h2")
        title = h2.get_text().strip() if h2 else ""

        # Summary
        summary_p = art.find("p", class_=lambda c: c and "line-clamp-2" in c)
        summary = summary_p.get_text().strip() if summary_p else ""

        # Image thumbnail
        img_tag = art.find("img")
        thumbnail_url = img_tag["src"] if img_tag and img_tag.get("src") else ""

        # Tags in article
        tags = []
        for tag_a in art.find_all("a", href=lambda h: h and "/templates?q=" in h):
            t_text = tag_a.get_text().strip()
            if t_text and t_text not in tags:
                tags.append(t_text)

        items.append({
            "id": slug,
            "title": title,
            "category": category,
            "summary": summary,
            "thumbnail_url": thumbnail_url,
            "tags": tags,
            "detail_url": urllib.parse.urljoin(BASE_URL, href),
        })

    next_a = soup.find("a", href=lambda h: h and "cursor=" in h)
    next_url = urllib.parse.urljoin(BASE_URL, next_a["href"]) if next_a and "下一页" in next_a.get_text() else None

    return items, next_url


def parse_detail_page(template_info):
    url = template_info["detail_url"]
    html = fetch_html(url)
    if not html:
        return template_info

    soup = BeautifulSoup(html, "html.parser")

    # Prompt text
    pre = soup.find("pre")
    prompt = pre.get_text().strip() if pre else ""

    # Original Image
    meta_img = soup.find("meta", {"property": "og:image"})
    original_img = meta_img["content"] if meta_img and meta_img.get("content") else ""
    if not original_img:
        # check img in page
        for img in soup.find_all("img"):
            if "original" in img.get("src", ""):
                original_img = img["src"]
                break

    # Meta attributes: 画面比例, 参考图, 建议尺寸, 适用行业
    aspect_ratio = "3:4"
    ref_images = ""
    rec_size = ""
    industries = ""

    for div in soup.find_all("div"):
        t = div.get_text().strip()
        if t.startswith("画面比例"):
            aspect_ratio = t.replace("画面比例", "").strip()
        elif t.startswith("参考图"):
            ref_images = t.replace("参考图", "").strip()
        elif t.startswith("建议尺寸"):
            rec_size = t.replace("建议尺寸", "").strip()
        elif t.startswith("适用行业"):
            industries = t.replace("适用行业", "").strip()

    # Detail tags
    detail_tags = list(template_info.get("tags", []))
    for a in soup.find_all("a", href=lambda h: h and "/templates?q=" in h):
        tag_t = a.get_text().strip()
        if tag_t and tag_t not in detail_tags:
            detail_tags.append(tag_t)

    # Local image filenames
    slug = template_info["id"]
    local_thumb = f"{slug}_thumb.jpg"
    local_orig = f"{slug}_orig.jpg"

    thumb_path = os.path.join(IMAGES_DIR, local_thumb)
    orig_path = os.path.join(IMAGES_DIR, local_orig)

    if template_info.get("thumbnail_url"):
        download_file(template_info["thumbnail_url"], thumb_path)
    if original_img:
        download_file(original_img, orig_path)

    template_info.update({
        "prompt": prompt,
        "original_image_url": original_img,
        "aspect_ratio": aspect_ratio,
        "reference_images": ref_images,
        "recommended_size": rec_size,
        "industries": industries,
        "tags": detail_tags,
        "local_thumbnail": f"/assets/cover_templates/{local_thumb}" if os.path.isfile(thumb_path) else (template_info.get("thumbnail_url") or ""),
        "local_original": f"/assets/cover_templates/{local_orig}" if os.path.isfile(orig_path) else (original_img or ""),
        "relative_thumbnail_path": f"data/cover_templates/images/{local_thumb}" if os.path.isfile(thumb_path) else "",
        "relative_original_path": f"data/cover_templates/images/{local_orig}" if os.path.isfile(orig_path) else "",
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })

    return template_info


def crawl_all():
    os.makedirs(IMAGES_DIR, exist_ok=True)

    print("🚀 开始爬取 Beav 封面提示词库...", flush=True)
    templates_map = {}
    current_url = LIST_URL
    page = 1

    while current_url:
        print(f"📄 正在抓取列表页 第 {page} 页: {current_url}", flush=True)
        html = fetch_html(current_url)
        if not html:
            break
        items, next_url = parse_listing_page(html)
        print(f"   抓取到 {len(items)} 个模板", flush=True)
        for item in items:
            templates_map[item["id"]] = item
        current_url = next_url
        page += 1
        time.sleep(0.5)

    all_templates = list(templates_map.values())
    total = len(all_templates)
    print(f"\n🔍 列表抓取完毕，共 {total} 个模板。开始并发抓取详情页和图片资源...", flush=True)

    detailed_templates = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(parse_detail_page, item): item["id"] for item in all_templates}
        done = 0
        for f in as_completed(futures):
            tid = futures[f]
            try:
                res = f.result()
                detailed_templates.append(res)
                done += 1
                if done % 5 == 0 or done == total:
                    print(f"   详情进度: {done}/{total} ({done/total*100:.1f}%)", flush=True)
            except Exception as e:
                print(f"[Error] Failed parsing detail for {tid}: {e}", flush=True)

    # 按列表原顺序排序
    detailed_templates.sort(key=lambda x: [item["id"] for item in all_templates].index(x["id"]))

    # 保存 JSON
    output_data = {
        "source": "https://www.getbeav.com/templates",
        "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": len(detailed_templates),
        "categories": sorted(list(set(t.get("category", "其他") for t in detailed_templates))),
        "templates": detailed_templates,
    }

    with open(TEMPLATES_JSON, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n💾 数据已成功保存到: {TEMPLATES_JSON}")

    # 生成 Markdown 索引文档
    md_lines = [
        "# Beav 社交媒体封面提示词库 (本地离线版)",
        "",
        f"> 来源：[https://www.getbeav.com/templates](https://www.getbeav.com/templates)  ",
        f"> 同步时间：{output_data['crawled_at']} ｜ 总模板数：**{len(detailed_templates)}** 套",
        "",
        "## 📚 分类目录",
        "",
    ]
    for cat in output_data["categories"]:
        cat_count = sum(1 for t in detailed_templates if t.get("category") == cat)
        md_lines.append(f"- **{cat}** ({cat_count} 款)")

    md_lines.append("\n---\n\n## 🎨 模板全览清单\n")

    for idx, t in enumerate(detailed_templates, 1):
        tags_str = " ".join([f"`#{tag}`" for tag in t.get("tags", [])])
        md_lines.extend([
            f"### {idx}. {t['title']}",
            f"- **分类**：{t['category']} ｜ **画面比例**：{t.get('aspect_ratio', '3:4')} ｜ **建议尺寸**：{t.get('recommended_size', '1K')}",
            f"- **适用行业**：{t.get('industries', '通用')} ｜ **参考图要求**：{t.get('reference_images', '无')}",
            f"- **标签**：{tags_str}",
            f"- **效果简述**：{t.get('summary', '')}",
            "",
            "<details>",
            "<summary><b>📋 点击查看完整 AI 提示词</b></summary>",
            "",
            "```text",
            t.get("prompt", "（暂无提示词）"),
            "```",
            "",
            "</details>",
            "",
            "---",
            "",
        ])

    with open(README_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"📖 索引文档已保存到: {README_MD}")

    return output_data


if __name__ == "__main__":
    crawl_all()
