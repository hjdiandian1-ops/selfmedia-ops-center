#!/usr/bin/env python3
import paramiko
import base64

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS

DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"
NAS_SHARED_DIR = "/volume1/docker/n8n/shared_files"
LOCAL_WORKFLOW = "/Users/xiaowuliao/Projects/自媒体发布agent/nas-n8n/workflows/hot_topic_radar.json"
REMOTE_WORKFLOW = "hot_topic_radar.json"

def import_workflow():
    print(f"📡 正在通过 SSH Base64 传输 n8n 工作流 {REMOTE_WORKFLOW} 并导入 n8n 容器...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)
    
    with open(LOCAL_WORKFLOW, "rb") as f:
        b64_content = base64.b64encode(f.read()).decode()
        
    remote_json_path = f"{NAS_SHARED_DIR}/{REMOTE_WORKFLOW}"
    exec_cmd = f"echo {NAS_PASS} | sudo -S bash -c 'echo {b64_content} | base64 -d > {remote_json_path} && chmod 777 {remote_json_path}'"
    stdin, stdout, stderr = ssh.exec_command(exec_cmd)
    stdout.read()
    print(f"✅ 工作流 JSON 文件传输成功: {remote_json_path}")
    
    # 查找运行中的 n8n 容器
    cmd_ps = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} ps --filter name=n8n -q"
    stdin, stdout, stderr = ssh.exec_command(cmd_ps)
    containers = stdout.read().decode("utf-8").strip().split("\n")
    
    for cid in containers:
        if cid:
            print(f"🐳 尝试在容器 ID {cid} 中执行 n8n import...")
            cmd_import = f"echo {NAS_PASS} | sudo -S {DOCKER_BIN} exec {cid} n8n import:workflow --input=/data/shared/{REMOTE_WORKFLOW}"
            stdin, stdout, stderr = ssh.exec_command(cmd_import)
            out = stdout.read().decode("utf-8")
            err = stderr.read().decode("utf-8")
            print(f"📥 导入日志:\n{out}\n{err}")

    ssh.close()

if __name__ == "__main__":
    import_workflow()
