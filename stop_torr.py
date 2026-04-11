import paramiko
HOST = '64.188.67.85'
USER = 'root'
PASS = 'VV1XrNJrRrByNOrh'
try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    print("Stopping torrserver...")
    client.exec_command('systemctl stop torrserver')
    stdin, stdout, stderr = client.exec_command('systemctl is-active torrserver')
    status = stdout.read().decode('utf-8').strip()
    print(f"TorrServer status: {status}")
    print("--- SYSTEM LOAD ---")
    stdin, stdout, stderr = client.exec_command('uptime')
    print(stdout.read().decode('utf-8'))
    client.close()
except Exception as e:
    print(f"Error: {e}")
