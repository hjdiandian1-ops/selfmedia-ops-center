import paramiko, json, base64

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

q_get = "SELECT row_to_json(w) FROM workflow_entity w WHERE id='Qald4KugzwLNNxQq';"
b64_q = base64.b64encode(q_get.encode()).decode()

write_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_q} | base64 -d > /volume1/docker/n8n/postgres_data/get_wf9.sql'"
stdin, stdout, stderr = ssh.exec_command(write_cmd)
stdout.read()

run_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -t -f /var/lib/postgresql/data/get_wf9.sql"
stdin, stdout, stderr = ssh.exec_command(run_cmd)
raw_wf = stdout.read().decode().strip()

wf = json.loads(raw_wf)
nodes = wf.get("nodes", [])

for n in nodes:
    if n.get("name") == "分支 1：小红书自动发布 (Playwright)":
        n["parameters"] = {
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
            "jsonBody": "={\n  \"title\": $json.title,\n  \"content\": $json.xhs_content,\n  \"images\": $json.images,\n  \"tags\": $json.tags,\n  \"cookies_json_path\": \"/data/shared/xhs_cookies.json\"\n}",
            "options": {}
        }
        n["continueOnFail"] = True

nodes_json_str = json.dumps(nodes, ensure_ascii=False)

sql_update = f"""
UPDATE workflow_entity 
SET nodes = '{nodes_json_str.replace("'", "''")}'::json
WHERE id = 'Qald4KugzwLNNxQq';
"""

b64_sql = base64.b64encode(sql_update.encode("utf-8")).decode("utf-8")
write_sql_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_sql} | base64 -d > /volume1/docker/n8n/postgres_data/fix_expr_mode.sql'"
stdin, stdout, stderr = ssh.exec_command(write_sql_cmd)
stdout.read()

run_update = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -f /var/lib/postgresql/data/fix_expr_mode.sql"
stdin, stdout, stderr = ssh.exec_command(run_update)
print("Update Expression Mode Out:\n", stdout.read().decode())

# Restart n8n container
print("🔄 重启 n8n 容器...")
restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart n8n"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("Restart Out:\n", stdout.read().decode())

ssh.close()
