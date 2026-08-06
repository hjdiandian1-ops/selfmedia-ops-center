import paramiko

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

# 1. Update WEBHOOK_URL in /volume1/docker/n8n/.env
print("🔧 1. 正在修正 NAS 上 n8n 的 .env 配置中的 WEBHOOK_URL 为 http://192.168.50.229:5678/ ...")
env_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo \"WEBHOOK_URL=http://192.168.50.229:5678/\" >> /volume1/docker/n8n/.env'"
stdin, stdout, stderr = ssh.exec_command(env_cmd)

# 2. Connect to n8n_postgres and query/cleanup workflows
print("🐘 2. 正在查询 n8n PostgreSQL 数据库中的工作流记录...")
sql_query = "SELECT id, name, active FROM workflow_entity;"
psql_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -c \"{sql_query}\""
stdin, stdout, stderr = ssh.exec_command(psql_cmd)
out = stdout.read().decode()
print("PostgreSQL 数据库中现有工作流:")
print(out)

# Delete duplicates, keeping only the first one
sql_clean = """
DELETE FROM workflow_entity WHERE id NOT IN (SELECT id FROM workflow_entity WHERE name LIKE '%小红书%' ORDER BY id LIMIT 1);
UPDATE workflow_entity SET active = true;
SELECT id, name, active FROM workflow_entity;
"""
psql_clean_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -c \"{sql_clean}\""
stdin, stdout, stderr = ssh.exec_command(psql_clean_cmd)
print("清理重复工作流并激活唯一工作流:")
print(stdout.read().decode())

# 3. Restart n8n container
print("🔄 3. 正在重启 n8n 容器以刷新 Webhook 注册表...")
restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart n8n"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("n8n 重启结果:", stdout.read().decode())

ssh.close()
