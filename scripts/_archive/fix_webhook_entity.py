import paramiko

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

sql1 = 'UPDATE webhook_entity SET \\"webhookPath\\"=\'publish-selfmedia\';'
cmd1 = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -c \"{sql1}\""
stdin, stdout, stderr = ssh.exec_command(cmd1)
print("Update out:\n", stdout.read().decode())

sql2 = 'SELECT * FROM webhook_entity;'
cmd2 = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -c \"{sql2}\""
stdin, stdout, stderr = ssh.exec_command(cmd2)
print("Select out:\n", stdout.read().decode())

restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart n8n"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("Restart out:\n", stdout.read().decode())

ssh.close()
