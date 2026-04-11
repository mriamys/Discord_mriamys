import paramiko

HOST = '64.188.67.85'
USER = 'root'
PASS = 'VV1XrNJrRrByNOrh'

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    
    stdin, stdout, stderr = client.exec_command("systemctl status mriamys.service")
    out = stdout.read().decode('utf-8', errors='ignore')
    print("STATUS:")
    print(out)
    
    stdin, stdout, stderr = client.exec_command("journalctl -u mriamys -n 20 --no-pager")
    logs = stdout.read().decode('utf-8', errors='ignore')
    print("LOGS:")
    print(logs)
    
    client.close()

if __name__ == '__main__':
    # Фикс для Windows
    import sys
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    main()
