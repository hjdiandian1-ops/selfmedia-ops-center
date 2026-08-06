import paramiko, json

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

# Fetch nodes
sql_get = "SELECT nodes FROM workflow_entity WHERE id='14NtoJ3MG9CQlrhE';"
psql_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -t -c \"{sql_get}\""
stdin, stdout, stderr = ssh.exec_command(psql_cmd)
raw_nodes = stdout.read().decode().strip()

nodes = json.loads(raw_nodes)
for n in nodes:
    if "webhook" in n.get("type", "").lower():
        n["webhookId"] = "publish-selfmedia"
        print("Updated Node:", json.dumps(n, indent=2, ensure_ascii=False))

updated_nodes_json = json.dumps(nodes, ensure_ascii=False).replace("'", "''")

# Update in PG
sql_update = f"UPDATE workflow_entity SET nodes='{updated_nodes_json}' WHERE id='14NtoJ3MG9CQlrhE';"
psql_update_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -c \"{sql_update}\""
stdin, stdout, stderr = ssh.exec_command(psql_update_cmd)
print("PG Update out:", stdout.read().decode())

# Restart n8n
restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart n8n"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("Restart out:", stdout.read().decode())

ssh.close()
