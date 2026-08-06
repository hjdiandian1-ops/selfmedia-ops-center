import paramiko, json

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

sql = "SELECT id, status, mode, \"workflowId\", \"stoppedAt\" FROM execution_entity ORDER BY id DESC LIMIT 5;"
psql_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -c \"{sql}\""
stdin, stdout, stderr = ssh.exec_command(psql_cmd)
print("Executions:\n", stdout.read().decode())

cmd_log = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} logs n8n --tail 25"
stdin, stdout, stderr = ssh.exec_command(cmd_log)
print("Logs:\n", stdout.read().decode())

ssh.close()
