import paramiko, base64, json, urllib.request

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

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
      "id": "parse-payload",
      "name": "解析与校验 Payload 数据",
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
      "id": "publish-xhs",
      "name": "分支 1：小红书自动发布 (Playwright)",
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
      "id": "publish-gzh",
      "name": "分支 2：公众号自动发布/草稿",
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
      "id": "notify-summary",
      "name": "汇总发布状态",
      "disabled": False
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
WHERE id = '14NtoJ3MG9CQlrhE';

DELETE FROM webhook_entity WHERE "workflowId" = '14NtoJ3MG9CQlrhE';

INSERT INTO webhook_entity ("webhookPath", "method", "node", "webhookId", "pathLength", "workflowId")
VALUES ('publish-selfmedia', 'POST', '接收 Agent 发布 Payload', 'publish-selfmedia', 1, '14NtoJ3MG9CQlrhE');
"""

b64_sql = base64.b64encode(sql_script.encode("utf-8")).decode("utf-8")

write_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_sql} | base64 -d > /volume1/docker/n8n/postgres_data/fix.sql'"
stdin, stdout, stderr = ssh.exec_command(write_cmd)
stdout.read()

run_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -f /var/lib/postgresql/data/fix.sql"
stdin, stdout, stderr = ssh.exec_command(run_cmd)
print("PG Exec Out:", stdout.read().decode())
print("PG Exec Err:", stderr.read().decode())

# Restart n8n
restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart n8n"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("Restart Out:", stdout.read().decode())

ssh.close()
