#!/usr/bin/env python3
import paramiko

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"

def publish_n8n_workflows():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)
    
    cmd_ps = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} ps --filter ancestor=blowsnow/n8n-chinese:latest -q"
    stdin, stdout, stderr = ssh.exec_command(cmd_ps)
    container_id = stdout.read().decode("utf-8").strip()
    
    if container_id:
        # 列出工作流
        cmd_list = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec {container_id} n8n list:workflows"
        stdin, stdout, stderr = ssh.exec_command(cmd_list)
        out_list = stdout.read().decode("utf-8")
        print("📋 n8n 中的工作流列表:")
        print(out_list)
        
        # 针对每个工作流激活发布
        import re
        ids = re.findall(r'\|\s*([A-Za-z0-9]{16})\s*\|', out_list)
        for w_id in ids:
            print(f"🚀 发布/激活工作流 ID: {w_id}")
            cmd_pub = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec {container_id} n8n publish:workflow --id={w_id}"
            stdin, stdout, stderr = ssh.exec_command(cmd_pub)
            print(stdout.read().decode("utf-8"))

    ssh.close()

if __name__ == "__main__":
    publish_n8n_workflows()
