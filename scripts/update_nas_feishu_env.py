#!/usr/bin/env python3
import os
import paramiko

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS

APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN", "")
TABLE_ID = os.environ.get("FEISHU_TABLE_ID", "")

def update_nas_env():
    print("📡 正在将完整飞书多维表格凭证写入 NAS 端 /volume1/docker/n8n/.env 文件...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)
    
    env_updates = [
        ("FEISHU_APP_ID", APP_ID),
        ("FEISHU_APP_SECRET", APP_SECRET),
        ("FEISHU_APP_TOKEN", APP_TOKEN),
        ("FEISHU_TABLE_ID", TABLE_ID),
    ]
    
    for key, val in env_updates:
        cmd_write = (
            f"echo {NAS_PASS} | sudo -S bash -c '"
            f"grep -q {key} /volume1/docker/n8n/.env && "
            f"sed -i \"s/{key}=.*/{key}={val}/\" /volume1/docker/n8n/.env || "
            f"echo \"{key}={val}\" >> /volume1/docker/n8n/.env'"
        )
        ssh.exec_command(cmd_write)
        
    print("✅ 已成功将所有飞书环境变量同步至 NAS .env 文件！")
    
    # 验证查看
    stdin, stdout, stderr = ssh.exec_command(f"echo {NAS_PASS} | sudo -S grep FEISHU /volume1/docker/n8n/.env")
    print("📄 NAS .env 中的飞书配置:")
    print(stdout.read().decode("utf-8"))

    ssh.close()

if __name__ == "__main__":
    update_nas_env()
