import paramiko, json, base64, time

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

print("🛑 Step 1: Stopping n8n container...")
stop_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} stop n8n"
stdin, stdout, stderr = ssh.exec_command(stop_cmd)
print("Stop:", stdout.read().decode().strip())

print("✏️  Step 2: Updating workflow nodes in DB...")
q_get = "SELECT row_to_json(w) FROM workflow_entity w WHERE id='Qald4KugzwLNNxQq';"
b64_q = base64.b64encode(q_get.encode()).decode()
write_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_q} | base64 -d > /volume1/docker/n8n/postgres_data/get_stopped.sql'"
stdin, stdout, stderr = ssh.exec_command(write_cmd)
stdout.read()
run_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -t -f /var/lib/postgresql/data/get_stopped.sql"
stdin, stdout, stderr = ssh.exec_command(run_cmd)
raw_wf = stdout.read().decode().strip()
wf = json.loads(raw_wf)
nodes = wf.get("nodes", [])

# The XHS Code node with proper $helpers.httpRequest syntax (valid in n8n 2.x)
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    returnFullResponse: false
  });
  result = typeof response === 'string' ? JSON.parse(response) : response;
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
        print(f"  ✅ Updated XHS node to Code node with this.helpers.httpRequest")
    elif n.get("name") == "分支 2：公众号自动发布/草稿":
        n["continueOnFail"] = True
        print(f"  ✅ Kept GZH node, set continueOnFail")

import uuid
new_version = str(uuid.uuid4())
nodes_json_str = json.dumps(nodes, ensure_ascii=False)

sql = f"""
UPDATE workflow_entity 
SET nodes = '{nodes_json_str.replace("'", "''")}'::json,
    "versionId" = '{new_version}',
    "activeVersionId" = '{new_version}',
    "updatedAt" = NOW()
WHERE id = 'Qald4KugzwLNNxQq';
"""

b64_sql = base64.b64encode(sql.encode("utf-8")).decode("utf-8")
write_sql = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_sql} | base64 -d > /volume1/docker/n8n/postgres_data/fix_stopped.sql'"
stdin, stdout, stderr = ssh.exec_command(write_sql)
stdout.read()
run_update = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -f /var/lib/postgresql/data/fix_stopped.sql"
stdin, stdout, stderr = ssh.exec_command(run_update)
print("  DB update:", stdout.read().decode().strip())

# Verify update
verify_q = "SELECT nodes->0->'type' as first_node_type, (SELECT nodes->2->'type' FROM workflow_entity WHERE id='Qald4KugzwLNNxQq') as xhs_type FROM workflow_entity WHERE id='Qald4KugzwLNNxQq';"
b64_v = base64.b64encode(verify_q.encode()).decode()
write_v = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_v} | base64 -d > /volume1/docker/n8n/postgres_data/verify.sql'"
stdin, stdout, stderr = ssh.exec_command(write_v)
stdout.read()
run_v = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -t -f /var/lib/postgresql/data/verify.sql"
stdin, stdout, stderr = ssh.exec_command(run_v)
print("  Verify:", stdout.read().decode().strip())

print("🚀 Step 3: Starting n8n container...")
start_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} start n8n"
stdin, stdout, stderr = ssh.exec_command(start_cmd)
print("Start:", stdout.read().decode().strip())

print("⏳ Waiting 15s for n8n to fully start...")
time.sleep(15)

# Check if n8n is up
check_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} ps --filter name=n8n --format '{{{{.Status}}}}'"
stdin, stdout, stderr = ssh.exec_command(check_cmd)
print("n8n status:", stdout.read().decode().strip())

ssh.close()
print("✅ Done - n8n should now use Code node for XHS publishing")
