import paramiko, json

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

sql_get = "SELECT row_to_json(w) FROM workflow_entity w WHERE id='14NtoJ3MG9CQlrhE';"
psql_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -t -c \"{sql_get}\""
stdin, stdout, stderr = ssh.exec_command(psql_cmd)
raw = stdout.read().decode().strip()

wf = json.loads(raw)
nodes = wf.get("nodes", [])

for n in nodes:
    if "webhook" in n.get("type", "").lower():
        n["webhookId"] = "publish-selfmedia"
        print("Updated Webhook Node:", json.dumps(n, indent=2, ensure_ascii=False))

nodes_json_str = json.dumps(nodes, ensure_ascii=False)

# Escape single quotes for SQL string literal
nodes_sql_escaped = nodes_json_str.replace("'", "''")

sql_update = f"UPDATE workflow_entity SET nodes = '{nodes_sql_escaped}'::json WHERE id = '14NtoJ3MG9CQlrhE';"

# Execute sql update using a temporary SQL file inside postgres container or stdin
ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(
    f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec -i n8n_postgres psql -U n8n -d n8n"
)
ssh_stdin.write(sql_update + "\n")
ssh_stdin.flush()
ssh_stdin.close()

out_update = ssh_stdout.read().decode()
err_update = ssh_stderr.read().decode()
print("SQL Update stdout:", out_update)
print("SQL Update stderr:", err_update)

# Restart n8n container
print("🔄 重启 n8n 容器...")
restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart n8n"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("Restart out:", stdout.read().decode())

ssh.close()
