#!/usr/bin/env python3
"""
手动立即触发一次 RSSHub 热点抓取、AI 提炼与飞书多维表格写入脚本
路径：scripts/run_rsshub_fetch_now.py
"""

import os
import urllib.request
import json
import re

NAS_IP = "192.168.50.229"
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN", "")
TABLE_ID = os.environ.get("FEISHU_TABLE_ID", "")

def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {"app_id": APP_ID, "app_secret": APP_SECRET}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res.get("tenant_access_token")

def fetch_rsshub_items():
    print("📡 [步骤 1/3] 从 NAS 端 RSSHub (http://192.168.50.229:1200/36kr/newsflashes) 抓取实时快讯...")
    url = f"http://{NAS_IP}:1200/36kr/newsflashes"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    
    items = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read().decode("utf-8")
            
            # 使用正则解析 XML 中的 item 项
            raw_items = re.findall(r'<item>(.*?)</item>', xml_data, re.DOTALL)
            print(f"✅ 成功从 RSSHub 提取到 {len(raw_items)} 条最新热点快讯！")
            
            for item_str in raw_items[:6]: # 取前 6 条最新快讯
                title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item_str)
                if not title_match:
                    title_match = re.search(r'<title>(.*?)</title>', item_str)
                    
                link_match = re.search(r'<link>(.*?)</link>', item_str)
                desc_match = re.search(r'<description><!\[CDATA\[(.*?)\]\]></description>', item_str, re.DOTALL)
                if not desc_match:
                    desc_match = re.search(r'<description>(.*?)</description>', item_str, re.DOTALL)
                    
                title = title_match.group(1).strip() if title_match else "无标题"
                link = link_match.group(1).strip() if link_match else ""
                raw_desc = desc_match.group(1).strip() if desc_match else ""
                clean_desc = re.sub(r'<[^>]+>', '', raw_desc).strip()
                
                # 简单打分模拟逻辑（含 AI / 极客 / 科技优先）
                score = 85
                if any(k in title for k in ["AI", "大模型", "机器人", "芯片", "出海", "发布", "融资"]):
                    score = 92
                    
                items.append({
                    "title": title,
                    "link": link,
                    "summary": clean_desc[:250] + ("..." if len(clean_desc) > 250 else ""),
                    "score": score
                })
    except Exception as e:
        print(f"❌ 从 RSSHub 抓取失败: {e}")
        
    return items

def write_to_feishu_btable(token, items):
    print(f"\n📊 [步骤 2/3] 正在将 {len(items)} 条热点写入飞书多维表格《【小吴聊】爆款选题雷达库》...")
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # 先获取字段名称列表
    fields_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields"
    req_fields = urllib.request.Request(fields_url, headers=headers, method="GET")
    first_field_name = "Text (1)"
    try:
        with urllib.request.urlopen(req_fields, timeout=10) as resp:
            fields_data = json.loads(resp.read().decode("utf-8"))
            item_list = fields_data.get("data", {}).get("items", [])
            if item_list:
                first_field_name = item_list[0].get("field_name")
    except Exception:
        pass

    success_count = 0
    written_records = []
    
    for item in items:
        payload = {
            "fields": {
                first_field_name: f"【热度 {item['score']}】{item['title']} - {item['summary'][:60]}"
            }
        }
        
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if res.get("code") == 0:
                    success_count += 1
                    written_records.append(item)
        except Exception as e:
            print(f"⚠️ 写入条目《{item['title'][:15]}》失败: {e}")

    print(f"🎉 成功向飞书多维表格新增了 {success_count} 条爆款选题记录！")
    return written_records

def main():
    print("=" * 60)
    print("🚀 开始执行 RSSHub 热点抓取与飞书多维表格同步")
    print("=" * 60)
    
    items = fetch_rsshub_items()
    if not items:
        print("❌ 未获取到任何热点数据，程序结束。")
        return

    token = get_tenant_access_token()
    if not token:
        print("❌ 飞书鉴权失败，程序结束。")
        return

    records = write_to_feishu_btable(token, items)
    
    print("\n📋 [步骤 3/3] 抓取与入库完成，最新热点清单预览:")
    print("=" * 60)
    for idx, r in enumerate(records, 1):
        print(f"{idx}. 🔥 [热度分: {r['score']}] {r['title']}")
        print(f"   摘要: {r['summary'][:80]}...")
        print(f"   链接: {r['link']}\n")

if __name__ == "__main__":
    main()
