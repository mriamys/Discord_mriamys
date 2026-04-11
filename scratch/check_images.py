import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('64.188.67.85', username='root', password='VV1XrNJrRrByNOrh')
stdin, stdout, stderr = c.exec_command("python3 -c \"with open('/root/Discord_mriamys/utils/images.py', 'r', encoding='utf-8') as f: lines=f.readlines(); [print(repr(l)) for l in lines if 'Стрик' in l]\"")
print(stdout.read().decode())
c.close()
