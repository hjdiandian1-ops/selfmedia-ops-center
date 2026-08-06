import paramiko, base64

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

sql_script = """
UPDATE workflow_entity 
SET "pinData" = '{}'::json,
    "settings" = '{"executionOrder": "v1"}'::json,
    "staticData" = '{}'::json,
    "meta" = '{}'::json,
    active = true
WHERE id = '14NtoJ3MG9CQlrhE';

DELETE FROM webhook_entity WHERE "workflowId" = '14NtoJ3MG9CQlrhE';

INSERT INTO webhook_entity ("webhookPath", "method", "node", "webhookId", "pathLength", "workflowId")
VALUES ('publish-selfmedia', 'POST', 'Webhook', 'publish-selfmedia', 1, '14NtoJ3MG9CQlrhE');
"""

b64_sql = base64.b64encode(sql_script.encode("utf-8")).decode("utf-8")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

# Write to postgres_data/fix.sql
write_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_sql} | base64 -d > /volume1/docker/n8n/postgres_data/fix.sql'"
stdin, stdout, stderr = ssh.exec_command(write_cmd)
stdout.read()

# Run psql in n8n_postgres container
run_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -f /var/lib/postgresql/data/fix.sql"
stdin, stdout, stderr = ssh.exec_command(run_cmd)
print("PSQL Out:\n", stdout.read().decode())
print("PSQL Err:\n", stderr.read().decode())

# Check updated workflow_entity
check_sql = "SELECT id, active, \"pinData\", \"settings\", \"meta\" FROM workflow_entity WHERE id='14NtoJ3MG9CQlrhE';"
check_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec n8n_postgres psql -U n8n -d n8n -c \"{check_sql}\""
stdin, stdout, stderr = ssh.exec_command(check_cmd)
print("Check Row:\n", stdout.read().decode())

# Restart n8n container
restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart n8n"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("Restart Out:\n", stdout.read().decode())

ssh.close()
