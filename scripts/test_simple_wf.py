import paramiko, json, base64

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

clean_wf = {
  "id": "k0Pa6zDRYdDHZZ3m",
  "name": "自媒体极速自动发布工作流",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "publish-selfmedia",
        "options": {}
      },
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 1,
      "position": [0, 0],
      "id": "webhook-node",
      "name": "Webhook",
      "webhookId": "publish-selfmedia"
    },
    {
      "parameters": {
        "jsCode": "return [{ json: { status: 'success', message: '🎉 自媒体自动发布任务已成功提交！' } }];"
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 1,
      "position": [300, 0],
      "id": "code-node",
      "name": "Code"
    }
  ],
  "connections": {
    "Webhook": {
      "main": [
        [
          {
            "node": "Code",
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
WHERE id = 'k0Pa6zDRYdDHZZ3m';

DELETE FROM webhook_entity WHERE "workflowId" = 'k0Pa6zDRYdDHZZ3m';

INSERT INTO webhook_entity ("webhookPath", "method", "node", "webhookId", "pathLength", "workflowId")
VALUES ('publish-selfmedia', 'POST', 'Webhook', 'publish-selfmedia', 1, 'k0Pa6zDRYdDHZZ3m');
"""

b64_sql = base64.b64encode(sql_script.encode("utf-8")).decode("utf-8")

write_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_sql} | base64 -d > /volume1/docker/n8n/postgres_data/simple_wf.sql'"
stdin, stdout, stderr = ssh.exec_command(write_cmd)
stdout.read()

run_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -f /var/lib/postgresql/data/simple_wf.sql"
stdin, stdout, stderr = ssh.exec_command(run_cmd)
print("PG Out:\n", stdout.read().decode())

# Restart n8n container
print("🔄 重启 n8n 容器...")
restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart n8n"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("Restart Out:\n", stdout.read().decode())

ssh.close()
