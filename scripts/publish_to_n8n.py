#!/usr/bin/env python3
import sys
import os
import json
import base64
import time
import argparse
import urllib.request
import urllib.parse
import paramiko
import shlex
from datetime import datetime

# ---------- NAS 配置（凭据从环境变量或 nas-n8n/.env 读取，禁止硬编码） ----------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_CANDIDATES = [
    os.path.join(_SCRIPT_DIR, "..", "nas-n8n", ".env"),
    os.path.join(_SCRIPT_DIR, "..", ".env"),
]


def _load_env_file():
    """极简 .env 加载（免依赖）：环境变量优先，文件仅补缺。"""
    for env_path in _ENV_CANDIDATES:
        env_path = os.path.normpath(env_path)
        if not os.path.exists(env_path):
            continue
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        return


_load_env_file()

NAS_IP = os.environ.get("NAS_IP", "192.168.50.229")
NAS_SSH_PORT = int(os.environ.get("NAS_SSH_PORT", "233"))
NAS_USER = os.environ.get("NAS_USER", "")
NAS_PASS = os.environ.get("NAS_PASS", "")
N8N_WEBHOOK_URL = f"http://{NAS_IP}:5678/webhook/publish-selfmedia"
NAS_SHARED_DIR = os.environ.get("NAS_SHARED_DIR", "/volume1/docker/n8n/shared_files")
XHS_PUBLISHER_PORT = int(os.environ.get("XHS_PUBLISHER_PORT", "5800"))

if not NAS_USER or not NAS_PASS:
    print("❌ 缺少 NAS 凭据：请在 nas-n8n/.env 配置 NAS_USER 与 NAS_PASS（参考 .env.example），或注入同名环境变量。")
    sys.exit(2)

def write_publish_log(job_id, title, success, platform="小红书"):
    """发布动作落盘 jobs/<job_id>/publish_log.json。
    与 scripts/collect_post_stats.py 同文件兼容(顶层 records 数组由数据回收追加)。
    """
    if not job_id:
        return None
    jobs_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jobs"))
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
    plats.add(platform)
    data["platforms"] = sorted(plats)
    data["publish"].append({
        "platform": platform,
        "status": "success" if success else "failed",
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"📝 发布记录已落盘：{path}")
    return path


def copy_images_to_nas(local_image_paths):
    """
    将本地生成的视觉卡片图片一键同步复制到 NAS 共享目录
    """
    if not local_image_paths:
        return []

    container_image_paths = []
    ssh = None
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=30)

        for idx, img_path in enumerate(local_image_paths):
            if not os.path.exists(img_path):
                print(f"⚠️ 警告: 本地图片路径不存在: {img_path}")
                continue

            filename = f"publish_img_{idx+1}_{os.path.basename(img_path)}"
            nas_remote_path = f"{NAS_SHARED_DIR}/{filename}"
            container_path = f"/data/shared/{filename}"

            try:
                with open(img_path, "rb") as f:
                    b64_data = base64.b64encode(f.read())

                # 密码通过 stdin 传入 sudo -S，不出现在命令行/进程列表（P0 安全修复）
                exec_cmd = ("sudo -S bash -c 'base64 -d > {} && chmod 777 {}'"
                            .format(shlex.quote(nas_remote_path), shlex.quote(nas_remote_path)))
                stdin, stdout, stderr = ssh.exec_command(exec_cmd)
                stdin.write(NAS_PASS + "\n" + b64_data.decode('ascii') + "\n")
                stdin.flush()
                stdin.close()

                stdout.read()
                container_image_paths.append(container_path)
                print(f"✅ 图片同步至 NAS 成功: {container_path}")
            except Exception as err:
                print(f"❌ 传输图片 {img_path} 失败: {err}")

    except Exception as e:
        print(f"⚠️ SSH 连接 NAS 失败: {e}")
    finally:
        if ssh:
            try:
                ssh.close()
            except Exception:
                pass

    return container_image_paths

def send_payload_to_n8n(title, xhs_content, gzh_html, container_images, tags, draft=False):
    """
    发送统一 Payload 到 NAS 端发布服务。
    【主链路】直连 xhs_publisher 发布微服务（实战验证的稳定链路）
    【降级链路】n8n Webhook（历史主链路常年 404，2026-08-04 起降为备用）
    """
    payload = {
        "title": title,
        "content": xhs_content,
        "xhs_content": xhs_content,
        "gzh_html": gzh_html,
        "images": container_images,
        "tags": tags,
        "cookies_json_path": "/data/shared/xhs_cookies.json"
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Antigravity-Agent-Publisher/1.0"
    }

    data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    # 草稿箱模式（P2）：公众号 HTML 进草稿，由手机端人工终审发布
    if draft:
        gzh_draft_url = f"http://{NAS_IP}:{XHS_PUBLISHER_PORT}/publish/gzh"
        draft_payload = {
            "title": title,
            "content": gzh_html or xhs_content,
            "images": [],
            "tags": [],
            "cookies_json_path": "/data/shared/gzh_cookies.json",
        }
        req_draft = urllib.request.Request(
            gzh_draft_url, data=json.dumps(draft_payload, ensure_ascii=False).encode("utf-8"),
            headers=headers, method="POST",
        )
        try:
            with urllib.request.urlopen(req_draft, timeout=120) as response:
                res_body = response.read().decode("utf-8")
                print(f"\n🎉 公众号草稿箱同步成功！响应状态: {response.status}")
                print(f"详细返回信息: {res_body}")
                return True
        except Exception as err:
            print(f"\n❌ 公众号草稿箱同步失败: {err}")
            return False

    # 尝试 1（主链路）: 直连 xhs_publisher 自动化发布微服务
    direct_url = f"http://{NAS_IP}:{XHS_PUBLISHER_PORT}/publish"
    req_direct = urllib.request.Request(direct_url, data=data_bytes, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req_direct, timeout=120) as response:
            res_body = response.read().decode("utf-8")
            print(f"\n🎉 成功通过 xhs_publisher 完成小红书自动发布！响应状态: {response.status}")
            print(f"详细返回信息: {res_body}")
            return True
    except Exception as err:
        print(f"\n⚠️ 主链路（xhs_publisher 直连）失败: {err}")
        print("🔄 降级尝试 n8n Webhook 链路...")

    # 尝试 2（降级链路）: n8n Webhook
    req = urllib.request.Request(N8N_WEBHOOK_URL, data=data_bytes, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode("utf-8")
            print(f"\n🎉 成功将发布任务提交至 n8n！响应状态: {response.status}")
            print(f"详细返回信息: {res_body}")
            return True
    except Exception as e:
        print(f"\n❌ 降级链路（n8n Webhook）同样失败: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="自媒体 Agent ➔ NAS n8n 一键发布连接器")
    parser.add_argument("--title", required=True, help="笔记/文章标题")
    parser.add_argument("--job-id", default="", help="Job ID（YYYY-MM-DD_主题名）；提供则发布后写 publish_log.json")
    parser.add_argument("--content", required=False, default="", help="小红书正文内容（webapp 允许留空）")
    parser.add_argument("--gzh-html", default="", help="公众号排版 HTML (可选)")
    parser.add_argument("--images", nargs="*", default=[], help="本地配图卡片文件路径列表")
    parser.add_argument("--tags", nargs="*", default=[], help="标签列表")
    parser.add_argument("--draft", action="store_true",
                        help="草稿箱模式：公众号 HTML 进草稿，人工手机端终审发布（不直发小红书）")

    args = parser.parse_args()

    print(f"🚀 开始执行一键发布流程: 《{args.title}》...")

    # 1. 传输本地配图到 NAS
    container_image_paths = copy_images_to_nas(args.images)

    # 1.5 若 --gzh-html 传的是本地文件路径，读取文件内容（草稿箱模式）
    gzh_html = args.gzh_html
    if gzh_html and os.path.exists(gzh_html):
        with open(gzh_html, "r", encoding="utf-8") as f:
            gzh_html = f.read()

    # 2. 触发 n8n 发布工作流
    platform = "公众号" if args.draft else "小红书"
    success = send_payload_to_n8n(
        title=args.title,
        xhs_content=args.content,
        gzh_html=gzh_html,
        container_images=container_image_paths,
        tags=args.tags,
        draft=args.draft,
    )

    if args.job_id:
        write_publish_log(args.job_id, args.title, success, platform=platform)

    if success:
        mode = "公众号草稿箱" if args.draft else "小红书自动发布队列"
        print(f"\n✨ [完成] 已成功分发至 NAS 并调起{mode}！")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
