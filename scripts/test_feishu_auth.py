#!/usr/bin/env python3
import os
import urllib.request
import json

APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

def test_feishu_auth():
    print(f"📡 正在测试飞书自建应用 OpenAPI 鉴权 (App ID: {APP_ID})...")
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {
        "app_id": APP_ID,
        "app_secret": APP_SECRET
    }
    
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("code") == 0:
                print(f"🎉 飞书 API 鉴权成功！获取到 tenant_access_token:")
                print(f"  > Token: {res.get('tenant_access_token')[:20]}...")
                print(f"  > 有效期: {res.get('expire')} 秒")
                return True
            else:
                print(f"❌ 飞书返回错误: {res}")
                return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

if __name__ == "__main__":
    test_feishu_auth()
