import paramiko

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

sql = "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
psql_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -t -c \"{sql}\""
stdin, stdout, stderr = ssh.exec_command(psql_cmd)
print("PostgreSQL Tables:\n", stdout.read().decode())

sql_wh = "SELECT * FROM webhook_entity;"
psql_wh_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -c \"{sql_wh}\""
stdin, stdout, stderr = ssh.exec_command(psql_wh_cmd)
print("webhook_entity:\n", stdout.read().decode())

ssh.close()
