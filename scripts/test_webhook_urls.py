#!/usr/bin/env python3
import urllib.request
import json

NAS_IP = "192.168.50.229"

def test_webhook(url_path):
    url = f"http://{NAS_IP}:5678/{url_path}"
    print(f"📡 测试 Webhook 连通性: {url}")
    payload = {"test": True, "title": "端到端测试"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"✅ 成功! HTTP {resp.status}: {resp.read().decode('utf-8')}")
            return True
    except Exception as e:
        print(f"❌ 失败 ({url_path}): {e}")
        return False

if __name__ == "__main__":
    test_webhook("webhook/publish-selfmedia")
    test_webhook("webhook-test/publish-selfmedia")
