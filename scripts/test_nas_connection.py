#!/usr/bin/env python3
import paramiko

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS

DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"
COMPOSE_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker-compose"

def check_docker_status():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)
    
    cmd = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} ps -a"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print("🐳 NAS 当前容器列表 (docker ps -a):")
    print(stdout.read().decode("utf-8"))

    ssh.close()

if __name__ == "__main__":
    check_docker_status()
