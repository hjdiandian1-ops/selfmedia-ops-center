import paramiko, base64, json

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

# Query latest 5 executions from execution_entity
sql = """
SELECT id, status, mode, "startedAt", "stoppedAt", "workflowId", data 
FROM execution_entity 
ORDER BY id DESC LIMIT 5;
"""

b64_sql = base64.b64encode(sql.encode("utf-8")).decode("utf-8")
write_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_sql} | base64 -d > /volume1/docker/n8n/postgres_data/inspect_execs.sql'"
stdin, stdout, stderr = ssh.exec_command(write_cmd)
stdout.read()

run_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -f /var/lib/postgresql/data/inspect_execs.sql"
stdin, stdout, stderr = ssh.exec_command(run_cmd)
output = stdout.read().decode()
print("Executions Output:\n", output[:3000])

ssh.close()
