#!/usr/bin/env python3
import urllib.request
import paramiko

NAS_IP = "192.168.50.229"
NAS_SSH_PORT = 233
from nas_config import NAS_IP, NAS_SSH_PORT, NAS_USER, NAS_PASS
DOCKER_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker"
COMPOSE_BIN = "/volume1/@appstore/ContainerManager/usr/bin/docker-compose"

def test_rsshub():
    print("📡 测试 1: 访问 NAS 端已运行的 RSSHub (http://192.168.50.229:1200/36kr/newsflashes)...")
    url = f"http://{NAS_IP}:1200/36kr/newsflashes"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            print(f"✅ RSSHub 状态良好！返回内容前 200 字:")
            print(content[:200])
    except Exception as e:
        print(f"❌ 访问 RSSHub 失败: {e}")

def check_n8n():
    print("\n📡 测试 2: 检查 NAS 端的 n8n 运行状态...")
    url = f"http://{NAS_IP}:5678/"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            print(f"✅ n8n 已经在运行中！HTTP Status: {resp.status}")
    except Exception as e:
        print(f"⚠️ n8n 未就绪或容器处于停止状态 ({e})。准备拉起 n8n 容器...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(NAS_IP, port=NAS_SSH_PORT, username=NAS_USER, password=NAS_PASS, timeout=10)
        
        cmd = f"cd /volume1/docker/n8n && echo {NAS_PASS} | sudo -S {COMPOSE_BIN} up -d"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print("🚀 执行 docker-compose up -d:")
        print(stdout.read().decode("utf-8"))
        print(stderr.read().decode("utf-8"))
        ssh.close()

if __name__ == "__main__":
    test_rsshub()
    check_n8n()
