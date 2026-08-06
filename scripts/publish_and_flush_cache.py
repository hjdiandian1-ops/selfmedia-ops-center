import paramiko, json, base64

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"
CID = "0edffb3e7cb4"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

# 1. Update versionId and activeVersionId to force cache invalidation
q_update_ver = """
UPDATE workflow_entity 
SET "versionId" = gen_random_uuid()::text,
    "activeVersionId" = gen_random_uuid()::text,
    active = true
WHERE id = 'Qald4KugzwLNNxQq';
"""
b64_sql = base64.b64encode(q_update_ver.encode("utf-8")).decode("utf-8")
write_sql_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_sql} | base64 -d > /volume1/docker/n8n/postgres_data/update_ver.sql'"
stdin, stdout, stderr = ssh.exec_command(write_sql_cmd)
stdout.read()

run_update = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -f /var/lib/postgresql/data/update_ver.sql"
stdin, stdout, stderr = ssh.exec_command(run_update)
print("Update Ver Out:\n", stdout.read().decode())

# 2. Call n8n publish:workflow
cmd_pub = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec {CID} n8n publish:workflow --id=Qald4KugzwLNNxQq"
stdin, stdout, stderr = ssh.exec_command(cmd_pub)
print("Publish CLI out:", stdout.read().decode())

# 3. Restart n8n container
print("🔄 重启 n8n 容器以加载最新编译缓存...")
restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart n8n"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("Restart out:", stdout.read().decode())

ssh.close()
