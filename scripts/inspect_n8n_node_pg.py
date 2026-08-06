import paramiko, json

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

sql = "SELECT nodes FROM workflow_entity WHERE id='14NtoJ3MG9CQlrhE';"
psql_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -t -c \"{sql}\""
stdin, stdout, stderr = ssh.exec_command(psql_cmd)
raw_nodes = stdout.read().decode()
try:
    nodes = json.loads(raw_nodes)
    for n in nodes:
        if "webhook" in n.get("type", "").lower():
            print("Webhook Node in DB:", json.dumps(n, indent=2, ensure_ascii=False))
except Exception as e:
    print("Err parsing nodes:", e, raw_nodes[:500])

ssh.close()
