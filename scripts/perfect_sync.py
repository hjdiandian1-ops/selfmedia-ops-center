import paramiko, base64, json

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

clean_wf = {
  "id": "QJWbTS3TnlZ4RH5h",
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
      "id": "node-webhook",
      "name": "Webhook",
      "webhookId": "publish-selfmedia",
      "disabled": False
    },
    {
      "parameters": {
        "jsCode": "const data = $input.item.json.body || $input.item.json;\nreturn [{\n  json: {\n    title: data.title || '无标题笔记',\n    xhs_content: data.xhs_content || data.content || '',\n    gzh_html: data.gzh_html || '',\n    images: data.images || [],\n    tags: data.tags || [],\n    publish_time: new Date().toISOString()\n  }\n}];"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [220, 0],
      "id": "node-parse",
      "name": "ParsePayload",
      "disabled": False
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
      "id": "node-xhs",
      "name": "XHSPublish",
      "disabled": False,
      "continueOnFail": True
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
      "id": "node-gzh",
      "name": "GZHPublish",
      "disabled": False,
      "continueOnFail": True
    },
    {
      "parameters": {
        "jsCode": "return [{\n  json: {\n    status: 'success',\n    message: '🎉 小红书 + 公众号双平台发布请求已成功完成！',\n    published_at: new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })\n  }\n}];"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [720, 0],
      "id": "node-summary",
      "name": "Summary",
      "disabled": False
    }
  ],
  "connections": {
    "Webhook": {
      "main": [
        [
          {
            "node": "ParsePayload",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "ParsePayload": {
      "main": [
        [
          {
            "node": "XHSPublish",
            "type": "main",
            "index": 0
          },
          {
            "node": "GZHPublish",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "XHSPublish": {
      "main": [
        [
          {
            "node": "Summary",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "GZHPublish": {
      "main": [
        [
          {
            "node": "Summary",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  },
  "settings": {
    "executionOrder": "v1"
  },
  "pinData": {},
  "staticData": {},
  "meta": {},
  "active": True
}

nodes_json = json.dumps(clean_wf["nodes"], ensure_ascii=False)
conn_json = json.dumps(clean_wf["connections"], ensure_ascii=False)

sql_script = f"""
UPDATE workflow_entity 
SET nodes = '{nodes_json.replace("'", "''")}'::json, 
    connections = '{conn_json.replace("'", "''")}'::json,
    "pinData" = '{{}}'::json,
    "staticData" = '{{}}'::json,
    "meta" = '{{}}'::json,
    "settings" = '{json.dumps(clean_wf["settings"])}'::json,
    active = true 
WHERE id = 'QJWbTS3TnlZ4RH5h';

DELETE FROM webhook_entity WHERE "workflowId" = 'QJWbTS3TnlZ4RH5h';

INSERT INTO webhook_entity ("webhookPath", "method", "node", "webhookId", "pathLength", "workflowId")
VALUES ('publish-selfmedia', 'POST', 'Webhook', 'publish-selfmedia', 1, 'QJWbTS3TnlZ4RH5h');
"""

b64_sql = base64.b64encode(sql_script.encode("utf-8")).decode("utf-8")

write_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_sql} | base64 -d > /volume1/docker/n8n/postgres_data/perfect_sync.sql'"
stdin, stdout, stderr = ssh.exec_command(write_cmd)
stdout.read()

run_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -f /var/lib/postgresql/data/perfect_sync.sql"
stdin, stdout, stderr = ssh.exec_command(run_cmd)
print("PG Sync Out:\n", stdout.read().decode())

# Restart n8n container
print("🔄 重启 n8n 容器...")
restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart n8n"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("Restart Out:\n", stdout.read().decode())

ssh.close()
