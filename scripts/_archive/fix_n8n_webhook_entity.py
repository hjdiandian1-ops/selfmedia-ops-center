import paramiko

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

sql_cmd = 'UPDATE webhook_entity SET "webhookPath" = \'publish-selfmedia\' WHERE "workflowId" = \'14NtoJ3MG9CQlrhE\';'
cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec -i n8n_postgres psql -U n8n -d n8n"

ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd)
ssh_stdin.write(sql_cmd + "\n")
ssh_stdin.flush()
ssh_stdin.close()

out = ssh_stdout.read().decode()
err = ssh_stderr.read().decode()
print("SQL Output:", out)
print("SQL Error:", err)

# Verify updated row
ssh_stdin2, ssh_stdout2, ssh_stderr2 = ssh.exec_command(cmd)
ssh_stdin2.write('SELECT * FROM webhook_entity;\n')
ssh_stdin2.flush()
ssh_stdin2.close()

print("Check Output:\n", ssh_stdout2.read().decode())

# Restart n8n
restart_cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart n8n"
stdin, stdout, stderr = ssh.exec_command(restart_cmd)
print("Restart out:", stdout.read().decode())

ssh.close()
