import paramiko
from scp import SCPClient
import os

HOST = '64.188.67.85'
USER = 'root'
PASS = 'VV1XrNJrRrByNOrh'

def create_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    return client

def upload_project(scp, local_path, remote_path):
    print(f"Uploading {local_path} to {remote_path}...")
    for item in os.listdir(local_path):
        if item in ['.git', '__pycache__', 'venv', 'deploy_bot.py']:
            continue
        s_item = os.path.join(local_path, item)
        if os.path.isfile(s_item):
            scp.put(s_item, remote_path=remote_path)
        elif os.path.isdir(s_item):
            scp.put(s_item, recursive=True, remote_path=remote_path)

commands = [
    "mkdir -p /root/Discord_mriamys",
    "export DEBIAN_FRONTEND=noninteractive",
    "apt-get update",
    "apt-get install -y python3-pip python3-venv ffmpeg mysql-server",
    # Setup venv
    "python3 -m venv /root/Discord_mriamys/venv",
    "/root/Discord_mriamys/venv/bin/pip install -r /root/Discord_mriamys/requirements.txt",
    # Setup DB
    "service mysql start",
    "mysql -e \"CREATE DATABASE IF NOT EXISTS mriamys_bot;\"",
    "mysql -e \"CREATE USER IF NOT EXISTS 'mriamys'@'localhost' IDENTIFIED BY 'password';\"",
    "mysql -e \"GRANT ALL PRIVILEGES ON mriamys_bot.* TO 'mriamys'@'localhost';\"",
    "mysql -e \"FLUSH PRIVILEGES;\"",
    # Setup SystemD
    "cp /root/Discord_mriamys/mriamys.service /etc/systemd/system/",
    "sed -i 's/python3 main.py/\\/root\\/Discord_mriamys\\/venv\\/bin\\/python3 main.py/g' /etc/systemd/system/mriamys.service",
    "systemctl daemon-reload",
    "systemctl enable mriamys.service",
    "systemctl restart mriamys.service"
]

def main():
    ssh = create_ssh_client()
    print("SSH Connected.")
    
    # 1. Create main dir
    ssh.exec_command("mkdir -p /root/Discord_mriamys")
    
    # 2. Upload files
    with SCPClient(ssh.get_transport()) as scp:
        upload_project(scp, "d:\\discord_bot", "/root/Discord_mriamys")
        
    print("Files uploaded. Running installation commands. This might take a few minutes...")
    
    # 3. Execute setup
    full_cmd = " && ".join(commands)
    stdin, stdout, stderr = ssh.exec_command(full_cmd)
    
    exit_status = stdout.channel.recv_exit_status()
    print("STDOUT:", stdout.read().decode())
    print("STDERR:", stderr.read().decode())
    print("Exit Status:", exit_status)
    
    ssh.close()

if __name__ == '__main__':
    main()
