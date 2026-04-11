import paramiko

HOST = '64.188.67.85'
USER = 'root'
PASS = 'VV1XrNJrRrByNOrh'

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    
    # Доустановка нужных либ
    client.exec_command("/root/Discord_mriamys/venv/bin/pip install pynacl cryptography")
    import time
    time.sleep(15) # ждем установку

    # Перезагружаем конфиги и стартуем бота
    client.exec_command("systemctl restart mriamys.service")
    
    time.sleep(3) # ждем инициализации
    
    stdin, stdout, stderr = client.exec_command("systemctl status mriamys.service")
    print("STATUS:")
    print(stdout.read().decode('utf-8', errors='ignore'))
    
    stdin, stdout, stderr = client.exec_command("journalctl -u mriamys -n 20 --no-pager")
    print("LOGS:")
    print(stdout.read().decode('utf-8', errors='ignore'))
    
    client.close()

if __name__ == '__main__':
    import sys
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    main()
