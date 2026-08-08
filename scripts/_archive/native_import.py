import paramiko

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"
CID = "0edffb3e7cb4"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

# 1. Truncate workflow tables cleanly in PostgreSQL
print("🧹 1. 正在清空 n8n 旧的重复工作流数据库...")
sql_clean = "TRUNCATE workflow_entity, webhook_entity CASCADE;"
cmd_clean = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -c \"{sql_clean}\""
stdin, stdout, stderr = ssh.exec_command(cmd_clean)
print("Clean DB out:", stdout.read().decode())

# 2. Native n8n import
print("📥 2. 正在通过原生 n8n CLI 导入工作流...")
cmd_import = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec {CID} n8n import:workflow --input=/data/shared/xhs_gzh_immediate_publish.json"
stdin, stdout, stderr = ssh.exec_command(cmd_import)
print("Import out:", stdout.read().decode())

# 3. Native n8n publish/activate
print("⚡️ 3. 正在激活工作流...")
sql_act = "UPDATE workflow_entity SET active = true;"
cmd_act = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -c \"{sql_act}\""
stdin, stdout, stderr = ssh.exec_command(cmd_act)
print("Activate out:", stdout.read().decode())

# 4. Check PostgreSQL rows
sql_check = "SELECT id, name, active FROM workflow_entity; SELECT * FROM webhook_entity;"
cmd_check = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -c \"{sql_check}\""
stdin, stdout, stderr = ssh.exec_command(cmd_check)
print("DB Status:\n", stdout.read().decode())

# 5. Restart n8n container
print("🔄 4. 重启 n8n 容器...")
restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart n8n"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("Restart out:", stdout.read().decode())

ssh.close()
