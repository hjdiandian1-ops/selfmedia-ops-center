import paramiko, json, base64

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"
JSON_FILE = "/volume1/docker/n8n/shared_files/xhs_gzh_immediate_publish.json"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

cmd = f"echo {NAS_PASS} | sudo -S cat {JSON_FILE}"
stdin, stdout, stderr = ssh.exec_command(cmd)
raw = stdout.read().decode()
wf = json.loads(raw)

# Fix the XHS HTTP Request node to use proper keypair body mode
# In n8n 2.x HTTP Request node, the CORRECT way to send JSON with dynamic values
# is using bodyParameters with key-value pairs in "keypair" specifyBody mode
for n in wf.get("nodes", []):
    if n.get("name") == "分支 1：小红书自动发布 (Playwright)":
        n["parameters"] = {
            "method": "POST",
            "url": "http://xhs-publisher:8000/publish",
            "sendHeaders": False,
            "sendBody": True,
            "specifyBody": "keypair",
            "bodyParameters": {
                "parameters": [
                    {"name": "title", "value": "={{ $json.title }}"},
                    {"name": "content", "value": "={{ $json.xhs_content }}"},
                    {"name": "images", "value": "={{ $json.images }}"},
                    {"name": "tags", "value": "={{ $json.tags }}"},
                    {"name": "cookies_json_path", "value": "/data/shared/xhs_cookies.json"}
                ]
            },
            "options": {}
        }
        n["continueOnFail"] = True
        print(f"✅ Fixed XHS node with keypair body mode")

    elif n.get("name") == "分支 2：公众号自动发布/草稿":
        n["parameters"] = {
            "method": "POST",
            "url": "http://creator_backend:3000/api/gzh/publish",
            "sendHeaders": False,
            "sendBody": True,
            "specifyBody": "keypair",
            "bodyParameters": {
                "parameters": [
                    {"name": "title", "value": "={{ $json.title }}"},
                    {"name": "content_html", "value": "={{ $json.gzh_html }}"}
                ]
            },
            "options": {}
        }
        n["continueOnFail"] = True
        print(f"✅ Fixed GZH node with keypair body mode")

# Write back to file
new_content = json.dumps(wf, ensure_ascii=False, indent=2)
b64 = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")

# Write via base64 decode to avoid shell escaping issues
write_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64} | base64 -d > {JSON_FILE}'"
stdin, stdout, stderr = ssh.exec_command(write_cmd)
stdout.read()
print("✅ File updated")

# Also update the workflow_entity DB with the same fix
# First stop n8n to prevent DB overwrite
print("🛑 Stopping n8n...")
stdin, stdout, stderr = ssh.exec_command(f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} stop n8n")
stdout.read()

# Read the DB workflow and update it too
q_get = "SELECT row_to_json(w) FROM workflow_entity w WHERE id='Qald4KugzwLNNxQq';"
b64_q = base64.b64encode(q_get.encode()).decode()
ssh.exec_command(f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_q} | base64 -d > /volume1/docker/n8n/postgres_data/get_for_json.sql'")[1].read()
raw_wf = ssh.exec_command(f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -t -f /var/lib/postgresql/data/get_for_json.sql")[1].read().decode().strip()
db_wf = json.loads(raw_wf)
db_nodes = db_wf.get("nodes", [])

for n in db_nodes:
    if n.get("name") == "分支 1：小红书自动发布 (Playwright)":
        n["type"] = "n8n-nodes-base.httpRequest"
        n["typeVersion"] = 4
        n["parameters"] = {
            "method": "POST",
            "url": "http://xhs-publisher:8000/publish",
            "sendHeaders": False,
            "sendBody": True,
            "specifyBody": "keypair",
            "bodyParameters": {
                "parameters": [
                    {"name": "title", "value": "={{ $json.title }}"},
                    {"name": "content", "value": "={{ $json.xhs_content }}"},
                    {"name": "images", "value": "={{ $json.images }}"},
                    {"name": "tags", "value": "={{ $json.tags }}"},
                    {"name": "cookies_json_path", "value": "/data/shared/xhs_cookies.json"}
                ]
            },
            "options": {}
        }
        n["continueOnFail"] = True
    elif n.get("name") == "分支 2：公众号自动发布/草稿":
        n["type"] = "n8n-nodes-base.httpRequest"
        n["typeVersion"] = 4
        n["parameters"] = {
            "method": "POST",
            "url": "http://creator_backend:3000/api/gzh/publish",
            "sendHeaders": False,
            "sendBody": True,
            "specifyBody": "keypair",
            "bodyParameters": {
                "parameters": [
                    {"name": "title", "value": "={{ $json.title }}"},
                    {"name": "content_html", "value": "={{ $json.gzh_html }}"}
                ]
            },
            "options": {}
        }
        n["continueOnFail"] = True

import uuid
new_ver = str(uuid.uuid4())
nodes_str = json.dumps(db_nodes, ensure_ascii=False)
sql = f"""UPDATE workflow_entity SET nodes='{nodes_str.replace("'","''")}'::json, "versionId"='{new_ver}', "activeVersionId"='{new_ver}', "updatedAt"=NOW() WHERE id='Qald4KugzwLNNxQq';"""
b64_sql = base64.b64encode(sql.encode("utf-8")).decode()
ssh.exec_command(f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_sql} | base64 -d > /volume1/docker/n8n/postgres_data/fix_both.sql'")[1].read()
result = ssh.exec_command(f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -f /var/lib/postgresql/data/fix_both.sql")[1].read().decode()
print("DB update:", result.strip())

print("🚀 Starting n8n...")
stdin, stdout, stderr = ssh.exec_command(f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} start n8n")
print("Start:", stdout.read().decode().strip())

ssh.close()
print("✅ Both JSON file and DB updated. n8n restarted.")
