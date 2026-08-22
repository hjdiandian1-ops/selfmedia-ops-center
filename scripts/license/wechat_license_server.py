#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号自动发码 Webhook 服务（卖家 NAS / 服务器常驻）
======================================================
零第三方依赖（基于 Python 标准库），可直接在 NAS / 软路由 / 云服务器运行。

功能：
1. 对接微信公众平台开发者模式（URL 验签与被动消息回复）；
2. 自动解析买家发送的「订单号 + 设备指纹码」；
3. 本地调用 Ed25519 私钥秒级签发 Pro Token 并回复给买家；
4. 记录发码日志到 data/issued_tokens.json，防止重复滥用与方便对账。

启动方式：
    python3 scripts/license/wechat_license_server.py --port 8088 --wechat-token selfmedia2026

微信公众平台后台配置（mp.weixin.qq.com -> 设置与开发 -> 基本配置 -> 服务器配置）：
    URL: http://<你的NAS公网域名或IP>:8088/wechat
    Token: selfmedia2026 (与命令行参数一致)
    消息加解密方式：明文模式（推荐）或兼容模式
"""
import argparse
import hashlib
import http.server
import json
import os
import re
import socketserver
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import license_lib as LL  # noqa: E402
import token_mint as TM  # noqa: E402

ISSUED_LOG = os.path.join(ROOT, "data", "issued_tokens.json")


def _load_issued():
    try:
        with open(ISSUED_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"orders": {}, "updated_at": ""}


def _save_issued(data):
    os.makedirs(os.path.dirname(ISSUED_LOG), exist_ok=True)
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ISSUED_LOG, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def verify_wechat_signature(token, signature, timestamp, nonce):
    """微信服务器接入验证：sha1(sort(token, timestamp, nonce)) == signature"""
    if not (token and signature and timestamp and nonce):
        return False
    items = sorted([token, timestamp, nonce])
    raw = "".join(items).encode("utf-8")
    return hashlib.sha1(raw).hexdigest() == signature


def build_text_reply(to_user, from_user, content):
    """构建微信公众号被动回复 XML 文本消息"""
    now_ts = int(time.time())
    return (
        f"<xml>\n"
        f"  <ToUserName><![CDATA[{to_user}]]></ToUserName>\n"
        f"  <FromUserName><![CDATA[{from_user}]]></FromUserName>\n"
        f"  <CreateTime>{now_ts}</CreateTime>\n"
        f"  <MsgType><![CDATA[text]]></MsgType>\n"
        f"  <Content><![CDATA[{content}]]></Content>\n"
        f"</xml>"
    )


def handle_user_message(xml_text):
    """解析用户微信消息并执行自动发码业务逻辑"""
    try:
        root = ET.fromstring(xml_text)
        to_user = root.findtext("ToUserName", "")
        from_user = root.findtext("FromUserName", "")
        msg_type = root.findtext("MsgType", "")
        content = root.findtext("Content", "").strip()
    except Exception as e:
        print(f"❌ XML 解析错误: {e}")
        return ""

    if msg_type != "text":
        return build_text_reply(from_user, to_user, "💡 您好！请发送文字消息获取专属 Pro 激活码。回复「帮助」查看发码格式。")

    raw_text = content.replace("，", " ").replace("：", " ").replace(":", " ")
    parts = [p.strip() for p in raw_text.split() if p.strip()]

    # 1. 帮助引导指令
    if not parts or parts[0] in ("帮助", "help", "指引", "激活码", "领码", "客服", "pro", "Pro"):
        help_msg = (
            "🎉 欢迎来到「自媒体运营中心」官方服务通道！\n\n"
            "【全自动领码格式】：\n"
            "请在本对话框直接回复：\n"
            "👉 激活 [面包多订单号] [设备指纹码]\n\n"
            "【示例】：\n"
            "激活 MBD20260816 mac_a13926d8acee4c205a26c6e2\n\n"
            "【获取设备码方法】：\n"
            "在项目终端运行：\n"
            "python3 scripts/license/install.py --show-fingerprint"
        )
        return build_text_reply(from_user, to_user, help_msg)

    # 2. 解析 订单号 与 设备指纹码
    # 格式兼容：`激活 ORD123 mac_xxx` 或 `ORD123 mac_xxx` 或 `mac_xxx ORD123`
    tokens = [p for p in parts if p not in ("激活", "兑换", "绑定", "发码")]
    if len(tokens) < 2:
        err_msg = (
            "⚠️ 格式未识别，请发送完整的订单号与设备码。\n\n"
            "👉 标准格式：激活 [订单号] [设备码]\n"
            "例如：激活 MBD20260816 mac_a13926d8acee4c205a26c6e2\n\n"
            "如遇疑问请留言，人工客服将尽快为您协助！"
        )
        return build_text_reply(from_user, to_user, err_msg)

    # 自动识别哪个是设备指纹码（包含下划线或较长十六进制），哪个是订单号
    order_id, device_bind = "", ""
    for t in tokens:
        if t.startswith(("mac_", "win_", "lnx_", "dev_", "fp_")) or len(t) >= 20:
            device_bind = t
        else:
            order_id = t

    if not order_id or not device_bind:
        # 默认按顺序分配
        order_id, device_bind = tokens[0], tokens[1]

    # 清洗设备码与订单号
    order_id = re.sub(r"[^\w\-]", "", order_id)[:60]
    device_bind = re.sub(r"[^\w\-]", "", device_bind)[:60]

    print(f"📥 收到发码请求 -> 买家 OpenID: {from_user}, 订单号: {order_id}, 设备码: {device_bind}")

    # 3. 检查防重发机制
    store = _load_issued()
    orders = store.setdefault("orders", {})
    existing = orders.get(order_id)
    if existing and existing.get("bind") == device_bind:
        token = existing.get("token")
        reply = (
            f"✅ 您此前已成功领取该订单的专属 Token：\n\n"
            f"{token}\n\n"
            f"👉 激活方式：在 Web 工作台右上角「设置 ➔ 授权激活」中粘贴即可！"
        )
        return build_text_reply(from_user, to_user, reply)

    # 4. 签发合法 Ed25519 Pro Token（默认 365 天年度 Pro）
    try:
        expiry_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        token = TM.mint(uid=order_id, tier="pro", expiry=expiry_date, bind=device_bind)
        
        # 记录发码
        orders[order_id] = {
            "openid": from_user,
            "bind": device_bind,
            "token": token,
            "exp": expiry_date,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        _save_issued(store)

        success_msg = (
            f"🎉 激活成功！您的专属 Pro Token 已签发：\n\n"
            f"{token}\n\n"
            f"【到期时间】：{expiry_date}\n"
            f"【绑定设备】：{device_bind}\n\n"
            f"👉【使用方法】：\n"
            f"打开自媒体运营中心 Web 工作台 ➔ 点击右上角「⚙️ 设置 ➔ 授权激活」➔ 粘贴此 Token 即可瞬间解锁全套 Pro 特权！"
        )
        print(f"✅ 成功自动签发 Token 给订单 {order_id} ({device_bind})")
        return build_text_reply(from_user, to_user, success_msg)

    except Exception as e:
        print(f"❌ 签发 Token 失败: {e}")
        fail_msg = f"❌ 签发失败：{e}\n请核对私钥配置或稍后重试，人工客服将很快为您处理。"
        return build_text_reply(from_user, to_user, fail_msg)


class WeChatWebhookHandler(http.server.BaseHTTPRequestHandler):
    wechat_token = "selfmedia2026"

    def do_GET(self):
        """处理微信服务器配置验证"""
        # 提取 query 参数
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        signature = qs.get("signature", [""])[0]
        timestamp = qs.get("timestamp", [""])[0]
        nonce = qs.get("nonce", [""])[0]
        echostr = qs.get("echostr", [""])[0]

        if verify_wechat_signature(self.wechat_token, signature, timestamp, nonce):
            print(f"✅ 微信服务器 URL 接入验证成功！")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(echostr.encode("utf-8"))
        else:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden: Invalid WeChat Signature")

    def do_POST(self):
        """处理买家发来的微信消息"""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="ignore")

        reply_xml = handle_user_message(body)
        if not reply_xml:
            reply_xml = "success"

        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.end_headers()
        self.wfile.write(reply_xml.encode("utf-8"))

    def log_message(self, format, *args):
        # 仅打印简要日志
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]} {args[1]}\n")


def daemonize(log_path):
    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    if os.fork() > 0:
        sys.exit(0)
    sys.stdout.flush()
    sys.stderr.flush()
    with open(os.devnull, "r") as dev_null:
        os.dup2(dev_null.fileno(), sys.stdin.fileno())
    log_fd = open(log_path, "a", encoding="utf-8")
    os.dup2(log_fd.fileno(), sys.stdout.fileno())
    os.dup2(log_fd.fileno(), sys.stderr.fileno())


def run_server(port=8088, token="selfmedia2026", daemon=False, log_file=""):
    if daemon:
        log_path = log_file or os.path.join(ROOT, "server.log")
        daemonize(log_path)

    WeChatWebhookHandler.wechat_token = token
    server_address = ("", port)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(server_address, WeChatWebhookHandler) as httpd:
        print(f"==================================================")
        print(f"🚀 微信公众号自动发码 Webhook 服务已启动")
        print(f"📡 监听端口: {port}")
        print(f"🔑 WeChat Token: {token}")
        print(f"🌐 微信后台填写 URL: http://<你的NAS公网地址>:{port}/wechat")
        print(f"==================================================")
        sys.stdout.flush()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止。")


def main():
    ap = argparse.ArgumentParser(description="微信公众号自动发码 Webhook 服务")
    ap.add_argument("--port", type=int, default=8088, help="服务监听端口（默认 8088）")
    ap.add_argument("--wechat-token", default="selfmedia2026", help="微信后台配置的 Token 字符串")
    ap.add_argument("--daemon", action="store_true", help="后台守护进程运行")
    ap.add_argument("--log", default="", help="日志文件路径")
    args = ap.parse_args()
    run_server(args.port, args.wechat_token, args.daemon, args.log)


if __name__ == "__main__":
    main()
