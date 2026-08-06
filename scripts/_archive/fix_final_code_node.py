import paramiko, json, base64

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

print("🛑 Stopping n8n...")
ssh.exec_command(f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} stop n8n")[1].read()

# Get current workflow
q_get = "SELECT row_to_json(w) FROM workflow_entity w WHERE id='Qald4KugzwLNNxQq';"
b64 = base64.b64encode(q_get.encode()).decode()
ssh.exec_command(f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64} | base64 -d > /volume1/docker/n8n/postgres_data/get_for_fix.sql'")[1].read()
raw = ssh.exec_command(f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -t -f /var/lib/postgresql/data/get_for_fix.sql")[1].read().decode().strip()
wf = json.loads(raw)
nodes = wf.get("nodes", [])

# Fix: use `json:` parameter (not `body:`) for proper JSON serialization
xhs_code = r"""
const data = $input.first().json;
const payload = {
  title: data.title,
  content: data.xhs_content,
  images: data.images,
  tags: data.tags,
  cookies_json_path: '/data/shared/xhs_cookies.json'
};

let result;
try {
  const response = await this.helpers.httpRequest({
    method: 'POST',
    url: 'http://xhs-publisher:8000/publish',
    json: payload
  });
  result = response;
} catch(e) {
  result = { error: e.message, status: 'xhs_failed' };
}

return [{ json: result }];
"""

for n in nodes:
    if n.get("name") == "分支 1：小红书自动发布 (Playwright)":
        n["type"] = "n8n-nodes-base.code"
        n["typeVersion"] = 2
        n["parameters"] = {
            "language": "javaScript",
            "jsCode": xhs_code
        }
        n["continueOnFail"] = True
        print("✅ Updated XHS node: using json: payload (not body: JSON.stringify)")

import uuid
new_ver = str(uuid.uuid4())
nodes_str = json.dumps(nodes, ensure_ascii=False)
sql = f"""UPDATE workflow_entity SET nodes='{nodes_str.replace("'","''")}'::json, "versionId"='{new_ver}', "activeVersionId"='{new_ver}', "updatedAt"=NOW() WHERE id='Qald4KugzwLNNxQq';"""
b64_sql = base64.b64encode(sql.encode("utf-8")).decode()
ssh.exec_command(f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_sql} | base64 -d > /volume1/docker/n8n/postgres_data/final_code_fix.sql'")[1].read()
result = ssh.exec_command(f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -f /var/lib/postgresql/data/final_code_fix.sql")[1].read().decode()
print("DB update:", result.strip())

print("🚀 Starting n8n...")
ssh.exec_command(f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} start n8n")[1].read()
print("✅ Done")

ssh.close()
