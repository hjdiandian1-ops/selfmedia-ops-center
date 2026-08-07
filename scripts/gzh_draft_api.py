#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公众号官方草稿箱 API（draft/add）—— 不依赖浏览器编辑器
=========================================================
流程：access_token → 上传封面（material/add_material）→ draft/add 存草稿。
凭据从 nas-n8n/.env 的 GZH_APP_ID / GZH_APP_SECRET 读取（禁止硬编码）。

用法：
    python3 scripts/gzh_draft_api.py \
        --title "标题" \
        --content-file outputs/<job>/公众号/<排版>.html \
        --cover outputs/<job>/小红书/封面.png \
        --author "小吴聊" \
        --digest "摘要（可选）" \
        --job-id 2026-08-06_主题名
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nas_config as NC  # noqa: E402

API_BASE = "https://api.weixin.qq.com"


def http_json(url, data=None, method="GET", headers=None, timeout=60):
    req = urllib.request.Request(url, data=data, method=method,
                                 headers=headers or {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get_access_token(appid, secret):
    url = (f"{API_BASE}/cgi-bin/token?grant_type=client_credential"
           f"&appid={urllib.parse.quote(appid)}&secret={urllib.parse.quote(secret)}")
    data = http_json(url)
    if "access_token" not in data:
        raise RuntimeError(f"获取 access_token 失败: {data}")
    return data["access_token"]


def _upload_file(access_token, path, url):
    """通用 multipart 图片上传，返回响应 JSON。"""
    boundary = "----codex-" + uuid.uuid4().hex
    filename = os.path.basename(path)
    with open(path, "rb") as f:
        file_bytes = f.read()
    ctype = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    parts = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'.encode())
    parts.append(f"Content-Type: {ctype}\r\n\r\n".encode())
    parts.append(file_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    return http_json(url, data=body, method="POST",
                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                     timeout=120)


def upload_cover(access_token, cover_path):
    """上传永久图片素材，返回 thumb_media_id。"""
    url = f"{API_BASE}/cgi-bin/material/add_material?access_token={access_token}&type=image"
    data = _upload_file(access_token, cover_path, url)
    if "media_id" not in data:
        raise RuntimeError(f"上传封面失败: {data}")
    return data["media_id"]


def upload_image_url(access_token, image_path):
    """上传正文图片，返回可插入 draft/add 正文的微信 URL。"""
    url = f"{API_BASE}/cgi-bin/media/uploadimg?access_token={access_token}"
    data = _upload_file(access_token, image_path, url)
    if "url" not in data:
        raise RuntimeError(f"正文图片上传失败: {data}")
    return data["url"]


def add_draft(access_token, title, content, thumb_media_id, author, digest):
    payload = {
        "articles": [{
            "title": title,
            "author": author,
            "digest": digest or "",
            "content": content,
            "content_source_url": "",
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
        }]
    }
    url = f"{API_BASE}/cgi-bin/draft/add?access_token={access_token}"
    data = http_json(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                     method="POST")
    if "media_id" not in data:
        raise RuntimeError(f"存草稿失败: {data}")
    return data


def write_publish_log(job_id, title, media_id, detail):
    if not job_id:
        return None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    jobs_dir = os.path.join(root, "jobs")
    path = os.path.join(jobs_dir, job_id, "publish_log.json")
    data = {"job_id": job_id, "records": []}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("records", [])
    data.setdefault("publish", [])
    data["published_at"] = data.get("published_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["title"] = title
    plats = set(data.setdefault("platforms", []))
    plats.add("公众号")
    data["platforms"] = sorted(plats)
    data["publish"].append({
        "platform": "公众号",
        "status": "success",
        "mode": "draft_api",
        "draft_media_id": media_id,
        "detail": detail,
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def main():
    ap = argparse.ArgumentParser(description="公众号官方草稿箱 API")
    ap.add_argument("--title", required=True)
    ap.add_argument("--content-file", required=True, help="gzh-design 输出的 HTML 文件")
    ap.add_argument("--cover", required=True, help="封面图片（PNG/JPG）")
    ap.add_argument("--author", default="小吴聊")
    ap.add_argument("--digest", default="")
    ap.add_argument("--job-id", default="")
    args = ap.parse_args()

    if not (NC.GZH_APP_ID and NC.GZH_APP_SECRET):
        print("❌ 缺少 GZH_APP_ID / GZH_APP_SECRET，请在 nas-n8n/.env 配置。")
        return 2
    with open(args.content_file, "r", encoding="utf-8") as f:
        content = f.read()
    if not os.path.exists(args.cover):
        print(f"❌ 封面不存在: {args.cover}")
        return 2
    digest = args.digest or re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", content))[:64].strip()

    print("① 获取 access_token ...")
    token = get_access_token(NC.GZH_APP_ID, NC.GZH_APP_SECRET)
    print("② 上传封面 ...")
    thumb_media_id = upload_cover(token, args.cover)
    print(f"   封面 media_id: {thumb_media_id[:12]}...")
    # ②.5 替换正文 [[IMG:路径]] 占位符为微信图 URL
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    placeholders = re.findall(r"\[\[IMG:([^\]]+)\]\]", content)
    for ph in placeholders:
        img_path = ph if os.path.isabs(ph) else os.path.join(root, ph)
        if not os.path.exists(img_path):
            print(f"❌ 正文图片不存在：{img_path}")
            return 2
        print(f"   上传正文图片：{img_path}")
        img_url = upload_image_url(token, img_path)
        content = content.replace(
            f"[[IMG:{ph}]]",
            f'<img src="{img_url}" style="max-width:100%;border-radius:8px;'
            'display:block;margin:16px auto;" />',
        )
    print("③ 调用 draft/add 存草稿 ...")
    result = add_draft(token, args.title, content, thumb_media_id, args.author, digest)
    media_id = result.get("media_id", "")
    print(f"🎉 草稿已保存！draft media_id: {media_id}")

    log_path = write_publish_log(args.job_id, args.title, media_id, result)
    if log_path:
        print(f"📝 发布记录已落盘：{log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
