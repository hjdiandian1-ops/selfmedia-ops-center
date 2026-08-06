#!/usr/bin/env python3
import paramiko

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

def restart_n8n():
    print("🔄 重启 NAS 端 n8n 容器以生效最新导入的工作流...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)
    
    cmd_ps = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} ps --filter ancestor=blowsnow/n8n-chinese:latest -q"
    stdin, stdout, stderr = ssh.exec_command(cmd_ps)
    container_id = stdout.read().decode("utf-8").strip()
    
    if container_id:
        print(f"🐳 正在重启容器 {container_id}...")
        cmd_restart = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} restart {container_id}"
        stdin, stdout, stderr = ssh.exec_command(cmd_restart)
        print(stdout.read().decode("utf-8"))
        print("✅ n8n 容器重启完成！")

    ssh.close()

if __name__ == "__main__":
    restart_n8n()
