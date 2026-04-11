import paramiko
import sys

HOST = '64.188.67.85'
USER = 'root'
PASS = 'VV1XrNJrRrByNOrh'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(HOST, username=USER, password=PASS)
    stdin, stdout, stderr = client.exec_command("journalctl -u mriamys -n 40 --no-pager")
    print(stdout.read().decode('utf-8'))
except Exception as e:
    print(e)
finally:
    client.close()
