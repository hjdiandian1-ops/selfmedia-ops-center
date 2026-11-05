#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Beav AI Skills 技能库本地全量爬虫脚本 (GetBeav Skills Crawler)
============================================================
从 https://www.getbeav.com/skills 及其子专题、发布者与标签页爬取全部 AI Skills：
1. 抓取所有技能卡片元数据（标题、作者、头像、版本、评分、推荐标签、更新日期等）；
2. 抓取技能详情页提取完整 pristine SKILL.md 规则正文（包含 YAML frontmatter 及系统提示词）；
3. 提取 GitHub 源码地址、作者小红书主页、风险等级、评论数等关键元数据；
4. 将头像图片本地化缓存至 data/skills_repo/avatars/；
5. 将每个技能单独保存为可直接调用的 Markdown 文件：data/skills_repo/skills/<slug>.md；
6. 生成全量结构化元数据：data/skills_repo/skills.json 与索引说明 data/skills_repo/README.md。
"""
import os
import sys
import json
import time
import re
import urllib.parse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

ROOT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUTPUT_DIR = os.path.join(ROOT_DIR, "data", "skills_repo")
SKILLS_DIR = os.path.join(OUTPUT_DIR, "skills")
AVATARS_DIR = os.path.join(OUTPUT_DIR, "avatars")
SKILLS_JSON = os.path.join(OUTPUT_DIR, "skills.json")
README_MD = os.path.join(OUTPUT_DIR, "README.md")

BASE_URL = "https://www.getbeav.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

SEED_URLS = [
    "https://www.getbeav.com/skills",
    "https://www.getbeav.com/skills?source=github",
    "https://www.getbeav.com/skills?source=community-curated",
    "https://www.getbeav.com/skills/redskill",
    "https://www.getbeav.com/skills/collections/baoyu",
    "https://www.getbeav.com/skills/collections/dbskill",
    "https://www.getbeav.com/skills/collections/redskill-xiaohongshu",
]

TAG_SEEDS = [
    "GitHub", "内容创作", "调研与选题", "内容诊断", "任务推进",
    "商业决策", "商业诊断", "dbskill", "dontbesilent", "图片制作",
]


def fetch_html(url, retries=3):
    """通过系统级 curl 绕过本地代理握手问题获取 HTML 文本"""
    for i in range(retries):
        try:
            cmd = ["curl", "-s", "-L", "--max-time", "15", "-A", HEADERS["User-Agent"], url]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
            if res.returncode == 0 and res.stdout:
                return res.stdout.decode("utf-8", errors="replace")
        except Exception as e:
            time.sleep(1 + i)
            if i == retries - 1:
                print(f"[Error] 获取页面失败 {url}: {e}", flush=True)
                return None
    return None


def download_file(url, target_path, retries=3):
    """下载图片文件到本地"""
    if os.path.isfile(target_path) and os.path.getsize(target_path) > 512:
        return True
    if not url:
        return False
    for i in range(retries):
        try:
            cmd = ["curl", "-s", "-L", "--max-time", "20", "-A", HEADERS["User-Agent"], "-o", target_path, url]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
            if res.returncode == 0 and os.path.isfile(target_path) and os.path.getsize(target_path) > 512:
                return True
        except Exception as e:
            time.sleep(1 + i)
            if i == retries - 1:
                print(f"[Warn] 下载文件失败 {url} -> {target_path}: {e}", flush=True)
                return False
    return False


def determine_category(slug: str, tags: list, collection: str = "") -> str:
    """根据 slug、标签及专题集合确定最贴合的高级分类"""
    s = slug.lower()
    t_str = " ".join(tags).lower()

    if "baoyu" in s or "baoyu" in collection or "宝玉" in t_str:
        return "宝玉创作技能"
    if s.startswith("dbs-") or "dbskill" in collection or "dbskill" in t_str or "商业" in t_str or "诊断" in t_str:
        return "商业决策与内容诊断"
    if (
        "xhs" in s
        or "redskill" in collection
        or s in ["atutun-xhs-cover", "xhs-visual-director-skill", "heytea", "2351179894"]
        or "小红书" in t_str
    ):
        return "小红书爆款"
    if (
        s in ["human-writing", "renhua", "writing-dna-skill", "affaan-m-ecc-brand-voice"]
        or "去ai味" in t_str
        or "人设" in t_str
        or "文风" in t_str
    ):
        return "文风拟人与去AI味"
    if s in ["high-retention-video-script", "gzh-design-skill"] or "视频" in t_str or "排版" in t_str:
        return "排版设计与视频"
    if (
        s.startswith("kostja94")
        or s.startswith("affaan-m-ecc")
        or s.startswith("openakita")
        or any(k in t_str for k in ["tiktok", "twitter", "x", "linkedin", "reddit"])
    ):
        return "社交营销与全平台"
    return "通用创作技能"


def parse_listing_cards(html, source_name="skills"):
    """解析技能列表页卡片"""
    soup = BeautifulSoup(html, "html.parser")
    cards = {}

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("/skills/"):
            continue
        if any(k in href for k in ["/collections/", "/publishers/", "/redskill"]) or href == "/skills":
            continue

        slug = href.replace("/skills/", "").split("?")[0].strip("/")
        if not slug:
            continue

        item = {
            "slug": slug,
            "url": f"https://www.getbeav.com/skills/{slug}",
            "tags": [],
            "source_origin": source_name,
        }

        # 提取头像
        img = a.find("img")
        if img and img.get("src"):
            item["avatar_url"] = img["src"]

        # 标题
        h2 = a.find("h2")
        if h2:
            item["title"] = h2.get_text().strip()

        # 评分与徽章
        text_spans = [s.get_text().strip() for s in a.find_all("span") if s.get_text().strip()]
        for t in text_spans:
            if re.match(r"^\d+\.\d+$", t):
                item["rating"] = t
            elif t in ["推荐", "社区精选", "GitHub", "RED skill"]:
                item["badge"] = t
            elif re.match(r"^\d+\.\d+(\.\d+)?$", t):
                item["version"] = t

        # 简介
        p_desc = a.find("p", class_=lambda c: c and "line-clamp" in c)
        if p_desc:
            item["summary"] = p_desc.get_text().strip()

        # 标签
        for span in a.find_all("span", class_=lambda c: c and "rounded-lg" in c):
            tag_text = span.get_text().strip()
            if tag_text and tag_text not in item["tags"] and len(tag_text) < 15:
                if not re.match(r"^\d", tag_text) and tag_text not in ["推荐", "社区精选", "低风险"]:
                    item["tags"].append(tag_text)

        cards[slug] = item
    return cards


def parse_detail_page(slug, html, card_info=None):
    """解析技能详情页，提取完整 SKILL.md、作者信息、GitHub、标签及元数据"""
    soup = BeautifulSoup(html, "html.parser")

    # 1. 核心正文：pre 中的原始 SKILL.md
    pre = soup.find("pre")
    skill_md = pre.get_text() if pre else ""

    # 2. 标题
    h1 = soup.find("h1")
    title = h1.get_text().strip() if h1 else (card_info.get("title") if card_info else slug)

    # 3. 简介
    meta_desc = soup.find("meta", {"name": "description"})
    summary = ""
    if meta_desc and "content" in meta_desc.attrs:
        summary = meta_desc["content"].strip()
    elif card_info and card_info.get("summary"):
        summary = card_info["summary"]

    # 4. 版本与角标
    version = (card_info.get("version") if card_info else "") or "1.0.0"
    badge = card_info.get("badge") if card_info else ""
    if h1 and h1.parent:
        for span in h1.parent.find_all("span"):
            t = span.get_text().strip()
            if re.match(r"^\d+\.\d+(\.\d+)?$", t):
                version = t
            elif "skill" in t.lower() or "red" in t.lower():
                badge = t

    # 5. 评分
    rating = (card_info.get("rating") if card_info else "") or "5.0"
    for span in soup.find_all("span"):
        t = span.get_text().strip()
        if re.match(r"^\d\.\d$", t):
            rating = t
            break

    # 6. 作者与发布者链接
    author = ""
    author_url = ""
    author_link = soup.find("a", href=lambda h: h and "/skills/publishers/" in h)
    if author_link:
        author = author_link.get_text().strip()
        author_url = urllib.parse.urljoin(BASE_URL, author_link["href"])
    elif card_info and card_info.get("author"):
        author = card_info["author"]

    # 7. 作者外链（如小红书个人主页、X、个人网站）
    author_profile = ""
    xhs_link = soup.find("a", href=lambda h: h and "xiaohongshu.com/user/profile" in h)
    if xhs_link:
        author_profile = xhs_link["href"]

    # 8. GitHub 源代码仓库
    github_url = ""
    for a in soup.find_all("a", href=lambda h: h and "github.com" in h):
        href = a["href"]
        if "Jamailar/Beav" not in href and "github.com/login" not in href:
            github_url = href
            break

    # 9. 更新日期
    updated_at = ""
    date_match = re.search(r"(\d{4}年\d{1,2}月\d{1,2}日)", html)
    if date_match:
        updated_at = date_match.group(1)

    # 10. 风险等级与评论数
    risk_level = "低风险"
    if "低风险" in html:
        risk_level = "低风险"
    elif "中风险" in html:
        risk_level = "中风险"
    elif "高风险" in html:
        risk_level = "高风险"

    comments_count = 0
    comm_match = re.search(r'lucide-message-square.*?<path[^>]*></path>\s*</svg>\s*(\d+)', html, re.DOTALL)
    if comm_match:
        comments_count = int(comm_match.group(1))

    # 11. 标签收集（页面 tag= 参数 + 卡片 tags）
    tags = list(card_info.get("tags", [])) if card_info else []
    for a in soup.find_all("a", href=lambda h: h and "tag=" in h):
        href = a["href"]
        param = href.split("tag=")[-1].split("&")[0]
        tag_val = urllib.parse.unquote(param).strip()
        if tag_val and tag_val not in tags and not tag_val.startswith("http"):
            tags.append(tag_val)

    # 头像
    avatar_url = (card_info.get("avatar_url") if card_info else "")
    if not avatar_url:
        img = soup.find("img", src=lambda s: s and ("github.com" in s or "avatars" in s))
        if img:
            avatar_url = img["src"]

    # 分类研判
    collection = ""
    if "baoyu" in slug or "jimliu" in slug:
        collection = "baoyu"
    elif slug.startswith("dbs-"):
        collection = "dbskill"
    elif "xhs" in slug or slug in ["atutun-xhs-cover", "heytea", "2351179894"]:
        collection = "redskill-xiaohongshu"

    category = determine_category(slug, tags, collection)

    return {
        "id": slug,
        "slug": slug,
        "title": title,
        "summary": summary,
        "category": category,
        "collection": collection,
        "tags": tags,
        "version": version,
        "badge": badge,
        "rating": rating,
        "author": author,
        "author_url": author_url,
        "author_profile": author_profile,
        "github_url": github_url,
        "avatar_url": avatar_url,
        "updated_at": updated_at,
        "risk_level": risk_level,
        "comments_count": comments_count,
        "source_url": f"https://www.getbeav.com/skills/{slug}",
        "skill_md": skill_md,
        "skill_md_path": f"skills/{slug}.md",
        "char_count": len(skill_md),
    }


def generate_readme(skills, categories, tags):
    """生成本地仓库说明文档 README.md"""
    lines = [
        "# Beav AI Skills 本地精选知识库",
        "",
        f"> **数据来源**: [GetBeav Skills 市场](https://www.getbeav.com/skills)  ",
        f"> **收录总量**: {len(skills)} 个独立生产力技能  ",
        f"> **更新时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        "",
        "本仓库已完整爬取 GetBeav 上收录的爆款自媒体创作、商业战略诊断与 AI 专家技能，包括宝玉系列（封面/信息图/配图/Markdown）、小红书 REDSkill 爆款视觉系列、dontbesilent 商业决策全套系统等。",
        "每个 Skill 均已本地化保存为标准的独立 `SKILL.md`，可无缝用于 Antigravity、Claude Code、Cursor、OpenAI 及各类自媒体生成工作流。",
        "",
        "## 目录导航",
        "",
    ]

    for cat, count in categories.items():
        lines.append(f"- [{cat} ({count})](#{cat.replace(' ', '-').lower()})")
    lines.append("")

    # 分类展示
    for cat, count in categories.items():
        lines.append(f"## {cat}")
        lines.append("")
        lines.append("| 技能名称 | Slug | 作者 | 版本 | 评分 | 核心功能简介 | 独立文件 |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        cat_skills = [s for s in skills if s["category"] == cat]
        for s in sorted(cat_skills, key=lambda x: x["title"]):
            file_link = f"[`{s['slug']}.md`](skills/{s['slug']}.md)"
            summary_short = s['summary'].replace('\n', ' ')[:45] + ('...' if len(s['summary']) > 45 else '')
            author_str = s['author'] or '-'
            lines.append(
                f"| **{s['title']}** | `{s['slug']}` | {author_str} | {s['version']} | ⭐ {s['rating']} | {summary_short} | {file_link} |"
            )
        lines.append("")

    lines.extend([
        "## 使用指南",
        "",
        "### 1. 独立文件直接引用",
        "在项目的各级 Agent、Skill 提示词或工作流中，可直接读取 `data/skills_repo/skills/<slug>.md` 作为系统提示词或参考规则。",
        "",
        "### 2. 运营中心可视化看板",
        "启动自媒体运营看板后，访问 `http://127.0.0.1:8787` 进入 **Skills 技能库** 模块：",
        "- 支持分类卡片筛选、标签点击过滤与全文即搜即显；",
        "- 点击任意卡片可弹出完整带语法高亮的 `SKILL.md` 窗口；",
        "- 提供“一键复制完整 Prompt”、“复制 SKILL.md”等快捷操作。",
        "",
    ])

    return "\n".join(lines)


def run_crawler():
    """爬虫主程序"""
    print("=" * 60, flush=True)
    print("🚀 开始爬取 GetBeav AI Skills 技能库...", flush=True)
    print("=" * 60, flush=True)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(SKILLS_DIR, exist_ok=True)
    os.makedirs(AVATARS_DIR, exist_ok=True)

    # 1. 发现所有技能卡片
    all_cards = {}
    print("\n[Step 1/4] 扫描索引页与专题集合...", flush=True)
    for url in SEED_URLS:
        print(f" -> 正在抓取: {url}", flush=True)
        html = fetch_html(url)
        if html:
            source_name = "redskill" if "redskill" in url else ("baoyu" if "baoyu" in url else "skills")
            cards = parse_listing_cards(html, source_name)
            all_cards.update(cards)
            print(f"    提取到 {len(cards)} 个技能卡片，累计发现 {len(all_cards)} 个", flush=True)

    # 补充扫描标签页
    for tag in TAG_SEEDS:
        tag_url = f"https://www.getbeav.com/skills?tag={urllib.parse.quote(tag)}"
        html = fetch_html(tag_url)
        if html:
            cards = parse_listing_cards(html, f"tag-{tag}")
            for k, v in cards.items():
                if k not in all_cards:
                    all_cards[k] = v
                elif tag not in all_cards[k]["tags"]:
                    all_cards[k]["tags"].append(tag)

    total_slugs = sorted(list(all_cards.keys()))
    print(f"\n[Step 1 完成] 共锁定 {len(total_slugs)} 个独立 AI Skills", flush=True)

    # 2. 多线程并发抓取技能详情页
    print(f"\n[Step 2/4] 并发抓取 {len(total_slugs)} 个技能详情页与完整 SKILL.md (5 并发)...", flush=True)
    detailed_skills = []

    def _fetch_one_skill(slug):
        card = all_cards.get(slug, {})
        url = f"https://www.getbeav.com/skills/{slug}"
        html = fetch_html(url)
        if not html:
            print(f"❌ 详情页抓取失败: {slug}", flush=True)
            return None
        detail = parse_detail_page(slug, html, card)
        print(f"✅ [{len(detail['skill_md']):5d} 字符] {detail['title']} ({slug})", flush=True)
        return detail

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_fetch_one_skill, slug): slug for slug in total_slugs}
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                detailed_skills.append(res)

    detailed_skills.sort(key=lambda x: x["slug"])
    print(f"\n[Step 2 完成] 成功提取 {len(detailed_skills)} 个技能完整数据！", flush=True)

    # 3. 本地化保存独立 .md 文件与头像
    print("\n[Step 3/4] 写入本地独立 Markdown 文件及缓存头像...", flush=True)
    for s in detailed_skills:
        slug = s["slug"]
        md_file = os.path.join(SKILLS_DIR, f"{slug}.md")
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(s["skill_md"])

        # 下载头像
        if s.get("avatar_url"):
            ext = ".png" if ".png" in s["avatar_url"] else ".jpg"
            avatar_path = os.path.join(AVATARS_DIR, f"{slug}{ext}")
            if download_file(s["avatar_url"], avatar_path):
                s["local_avatar"] = f"/assets/skills_repo/{slug}{ext}"
            else:
                s["local_avatar"] = s["avatar_url"]
        else:
            s["local_avatar"] = ""

    # 4. 生成聚合统计与结构化输出
    print("\n[Step 4/4] 生成 JSON 元数据与 README.md 索引...", flush=True)
    category_counts = {}
    all_tags = set()
    for s in detailed_skills:
        c = s["category"]
        category_counts[c] = category_counts.get(c, 0) + 1
        for t in s["tags"]:
            all_tags.add(t)

    result_json = {
        "total_count": len(detailed_skills),
        "source": "https://www.getbeav.com/skills",
        "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "category_counts": category_counts,
        "categories": ["全部"] + sorted(list(category_counts.keys())),
        "tags": sorted(list(all_tags)),
        "skills": detailed_skills,
    }

    with open(SKILLS_JSON, "w", encoding="utf-8") as f:
        json.dump(result_json, f, ensure_ascii=False, indent=2)

    readme_content = generate_readme(detailed_skills, category_counts, all_tags)
    with open(README_MD, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("\n" + "=" * 60, flush=True)
    print(f"🎉 爬虫执行完毕！收录总数: {len(detailed_skills)} 个", flush=True)
    print(f"📁 独立 Markdown 目录: {SKILLS_DIR}", flush=True)
    print(f"📄 元数据文件: {SKILLS_JSON}", flush=True)
    print(f"📑 索引文档: {README_MD}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    run_crawler()
