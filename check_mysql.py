import paramiko
HOST = '64.188.67.85'
USER = 'root'
PASS = 'VV1XrNJrRrByNOrh'
try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    
    print("--- VMSTAT (CPU/MEM/IO) ---")
    stdin, stdout, stderr = client.exec_command('vmstat 1 5')
    print(stdout.read().decode('utf-8'))
    
    print("\n--- MYSQL PROCESSLIST ---")
    # Trying with mysql command without interactive shell issues
    stdin, stdout, stderr = client.exec_command('mysql -u root -e "SHOW FULL PROCESSLIST;"')
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    if out: print(out)
    if err: print(f"MySQL Error: {err}")
    
    print("\n--- SYSTEM LOAD ---")
    stdin, stdout, stderr = client.exec_command('uptime')
    print(stdout.read().decode('utf-8'))
    
    client.close()
except Exception as e:
    print(f"Error: {e}")
