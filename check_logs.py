import paramiko
import sys

HOST = '64.188.67.85'
USER = 'root'
PASS = 'VV1XrNJrRrByNOrh'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(HOST, username=USER, password=PASS)
    stdin, stdout, stderr = client.exec_command("cd /root/Discord_mriamys && source venv/bin/activate && python3 -c 'import nacl.secret; print(nacl.__version__)'")
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    print("OUT:", out)
    print("ERR:", err)
except Exception as e:
    print(e)
finally:
    client.close()
