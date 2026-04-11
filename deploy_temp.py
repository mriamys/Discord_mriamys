import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('64.188.67.85', username='root', password='VV1XrNJrRrByNOrh')

# find the repo
stdin, stdout, stderr = client.exec_command('ls -l /root/Discord_mriamys')
out = stdout.read().decode('utf-8').strip()
print("dir check:", out)

if "mriamys.py" in out or "main.py" in out or "requirements.txt" in out:
    print("Found repo at /root/Discord_mriamys")
    # Pull and restart
    stdin, stdout, stderr = client.exec_command('cd /root/Discord_mriamys && git pull origin master && systemctl restart mriamys')
    print("pull output:", stdout.read().decode('utf-8'))
    print("pull stderr:", stderr.read().decode('utf-8'))
else:
    print("Not found in /root/Discord_mriamys, trying to find it...")
    stdin, stdout, stderr = client.exec_command('find / -name "cogs" -type d 2>/dev/null | grep mriamys')
    print("find output:", stdout.read().decode('utf-8'))

client.close()
