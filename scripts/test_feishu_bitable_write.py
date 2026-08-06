#!/usr/bin/env python3
import os
import urllib.request
import json

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

def write_test_record(token):
    print(f"📡 正在测试向飞书多维表格新增记录 (App Token: {APP_TOKEN}, Table ID: {TABLE_ID})...")
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # 获取表格现有的字段信息
    fields_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields"
    req_fields = urllib.request.Request(fields_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req_fields, timeout=10) as resp:
            fields_data = json.loads(resp.read().decode("utf-8"))
            print("📋 表格现有字段:")
            items = fields_data.get("data", {}).get("items", [])
            for item in items:
                print(f"  - {item.get('field_name')} ({item.get('type')})")
    except Exception as e:
        print(f"⚠️ 获取字段列表警告: {e}")

    # 尝试插入第一条测试记录
    payload = {
        "fields": {}
    }
    
    # 尝试写入现有第一列
    if items:
        first_field_name = items[0].get("field_name")
        payload["fields"][first_field_name] = "全网首发：我的 NAS + AI 自媒体全自动发布系统搭建全过程"
    else:
        payload["fields"]["文本"] = "全网首发：我的 NAS + AI 自媒体全自动发布系统搭建全过程"

    data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("code") == 0:
                record_id = res.get("data", {}).get("record", {}).get("record_id")
                print(f"🎉 记录写入成功！Record ID: {record_id}")
                return True
            else:
                print(f"❌ 写入记录失败: {res}")
                return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def main():
    token = get_tenant_access_token()
    if token:
        write_test_record(token)

if __name__ == "__main__":
    main()
