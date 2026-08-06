import paramiko, json

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

sql = "SELECT row_to_json(w) FROM workflow_entity w WHERE id='14NtoJ3MG9CQlrhE';"
psql_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -t -c \"{sql}\""
stdin, stdout, stderr = ssh.exec_command(psql_cmd)
raw = stdout.read().decode().strip()

wf = json.loads(raw)
for k, v in wf.items():
    if k not in ["nodes", "connections"]:
        print(f"Key '{k}': {v}")
    else:
        print(f"Key '{k}': type={type(v).__name__}")

ssh.close()
