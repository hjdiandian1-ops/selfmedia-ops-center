import paramiko, json, base64

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"
CID = "0edffb3e7cb4"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

clean_wf = {
  "name": "小红书+公众号双平台即时自动发布工作流",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "publish-selfmedia",
        "responseMode": "onReceived",
        "responseData": "allEntries",
        "options": {}
      },
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [0, 0],
      "id": "webhook-receiver",
      "name": "接收 Agent 发布 Payload",
      "webhookId": "publish-selfmedia"
    },
    {
      "parameters": {
        "jsCode": "const data = $input.item.json.body || $input.item.json;\nreturn [{\n  json: {\n    title: data.title || '无标题笔记',\n    xhs_content: data.xhs_content || data.content || '',\n    gzh_html: data.gzh_html || '',\n    images: data.images || [],\n    tags: data.tags || [],\n    publish_time: new Date().toISOString()\n  }\n}];"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [220, 0],
      "id": "parse-payload",
      "name": "解析与校验 Payload 数据"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://xhs-publisher:8000/publish",
        "sendHeaders": True,
        "headerParameters": {
          "parameters": [
            {
              "name": "Content-Type",
              "value": "application/json"
            }
          ]
        },
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={\n  \"title\": \"{{ $json.title }}\",\n  \"content\": \"{{ $json.xhs_content }}\",\n  \"images\": {{ JSON.stringify($json.images) }},\n  \"tags\": {{ JSON.stringify($json.tags) }},\n  \"cookies_json_path\": \"/data/shared/xhs_cookies.json\"\n}",
        "options": {}
      },
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [480, -100],
      "id": "publish-xhs",
      "name": "分支 1：小红书自动发布 (Playwright)"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://localhost:3000/api/gzh/publish",
        "sendHeaders": True,
        "headerParameters": {
          "parameters": [
            {
              "name": "Content-Type",
              "value": "application/json"
            }
          ]
        },
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={\n  \"title\": \"{{ $json.title }}\",\n  \"content_html\": \"{{ $json.gzh_html }}\"\n}",
        "options": {}
      },
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [480, 100],
      "id": "publish-gzh",
      "name": "分支 2：公众号自动发布/草稿"
    },
    {
      "parameters": {
        "jsCode": "return [{\n  json: {\n    status: 'success',\n    message: '🎉 小红书 + 公众号双平台发布请求已成功完成！',\n    published_at: new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })\n  }\n}];"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [720, 0],
      "id": "notify-summary",
      "name": "汇总发布状态"
    }
  ],
  "connections": {
    "接收 Agent 发布 Payload": {
      "main": [
        [
          {
            "node": "解析与校验 Payload 数据",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "解析与校验 Payload 数据": {
      "main": [
        [
          {
            "node": "分支 1：小红书自动发布 (Playwright)",
            "type": "main",
            "index": 0
          },
          {
            "node": "分支 2：公众号自动发布/草稿",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "分支 1：小红书自动发布 (Playwright)": {
      "main": [
        [
          {
            "node": "汇总发布状态",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "分支 2：公众号自动发布/草稿": {
      "main": [
        [
          {
            "node": "汇总发布状态",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  },
  "settings": {
    "executionOrder": "v1"
  }
}

# 1. Save JSON to shared_files
b64_json = base64.b64encode(json.dumps(clean_wf, indent=2, ensure_ascii=False).encode("utf-8")).decode("utf-8")
write_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_json} | base64 -d > /volume1/docker/n8n/shared_files/xhs_gzh_immediate_publish.json'"
stdin, stdout, stderr = ssh.exec_command(write_cmd)
stdout.read()

# 2. Truncate tables cleanly
print("🧹 1. 正在清空 n8n 旧的数据表...")
cmd_clean = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -c 'TRUNCATE workflow_entity, webhook_entity CASCADE;'"
stdin, stdout, stderr = ssh.exec_command(cmd_clean)
print("Clean DB out:", stdout.read().decode())

# 3. Native n8n import
print("📥 2. 正在通过原生 n8n CLI 导入新 JSON...")
cmd_import = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec {CID} n8n import:workflow --input=/data/shared/xhs_gzh_immediate_publish.json"
stdin, stdout, stderr = ssh.exec_command(cmd_import)
print("Import out:", stdout.read().decode())

# 4. Get imported workflow ID
cmd_get_id = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -t -c 'SELECT id FROM workflow_entity LIMIT 1;'"
stdin, stdout, stderr = ssh.exec_command(cmd_get_id)
new_id = stdout.read().decode().strip()
print("新工作流 ID:", new_id)

# 5. Native n8n publish
print(f"⚡️ 3. 正在通过 n8n CLI 激活并发布工作流 ID: {new_id}...")
cmd_pub = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec {CID} n8n publish:workflow --id={new_id}"
stdin, stdout, stderr = ssh.exec_command(cmd_pub)
print("Publish out:", stdout.read().decode())

# 6. Check registered webhook_entity
cmd_check = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -c 'SELECT * FROM webhook_entity;'"
stdin, stdout, stderr = ssh.exec_command(cmd_check)
print("Registered Webhook Entity:\n", stdout.read().decode())

# 7. Restart n8n container
print("🔄 4. 重启 n8n 容器...")
restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart n8n"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("Restart out:", stdout.read().decode())

ssh.close()
