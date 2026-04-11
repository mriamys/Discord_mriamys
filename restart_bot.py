import paramiko
HOST = '64.188.67.85'
USER = 'root'
PASS = 'VV1XrNJrRrByNOrh'
try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    print("Restarting discord bot...")
    client.exec_command('systemctl restart mriamys')
    client.close()
    print("Done")
except Exception as e:
    print(f"Error: {e}")
