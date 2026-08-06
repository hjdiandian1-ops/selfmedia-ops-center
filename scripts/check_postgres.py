import paramiko

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)

cmd = f"echo {NAS_PASS} | sudo -S cat /volume1/docker/n8n/docker-compose.yml"
stdin, stdout, stderr = ssh.exec_command(cmd)
print("Compose out:\n", stdout.read().decode())
ssh.close()
