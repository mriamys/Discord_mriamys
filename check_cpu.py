import paramiko
HOST = '64.188.67.85'
USER = 'root'
PASS = 'VV1XrNJrRrByNOrh'
try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    print("--- TOP 20 PROCESSES BY CPU ---")
    stdin, stdout, stderr = client.exec_command('ps -eo pid,pcpu,pmem,rss,vsz,comm,args --sort=-pcpu | head -n 20')
    print(stdout.read().decode('utf-8'))
    print("--- SYSTEM LOAD ---")
    stdin, stdout, stderr = client.exec_command('uptime')
    print(stdout.read().decode('utf-8'))
    print("--- FREE MEMORY ---")
    stdin, stdout, stderr = client.exec_command('free -m')
    print(stdout.read().decode('utf-8'))
    client.close()
except Exception as e:
    print(f"Error: {e}")
