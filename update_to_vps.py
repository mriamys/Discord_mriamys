import paramiko
import subprocess
import sys
import os

HOST = '64.188.67.85'
USER = 'root'
PASS = 'VV1XrNJrRrByNOrh'

def main():
    print("--- [ШАГ 1] пуш на GitHub ---")
    try:
        subprocess.run(["git", "add", "."], check=True)
        # Если статус пустой (нечего коммитить)
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if status.stdout.strip():
            subprocess.run(["git", "commit", "-m", "Auto-update from Mriamys Agent Tracker"], check=True)
        subprocess.run(["git", "push", "origin", "master"], check=True)
        print("✅ Изменения успешно залиты на GitHub!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при пуше на GitHub (возможно нет новых изменений): {e}")

    print("\n--- [ШАГ 2] обновление на VPS ---")
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(HOST, username=USER, password=PASS)

        # Выполняем команды. Если папка на сервере не git репо, инициализируем ее
        commands = [
            "cd /root/Discord_mriamys",
            "git init",
            "git remote add origin https://github.com/mriamys/Discord_mriamys.git || true",
            "git fetch origin master",
            "git reset --hard origin/master",
            "apt-get update && apt-get install -y ffmpeg libsodium-dev",
            "pip3 install -r requirements.txt",
            "systemctl restart mriamys.service"
        ]
        full_cmd = " && ".join(commands)
        
        print("🔗 Подключено к VPS. Выполняю pull и перезапуск сервиса...")
        stdin, stdout, stderr = client.exec_command(full_cmd)
        
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode('utf-8', errors='ignore')
        err = stderr.read().decode('utf-8', errors='ignore')
        
        if exit_code == 0:
            print("✅ Бот на VPS успешно обновлен и перезапущен!")
            print(out)
        else:
            print("❌ Произошла ошибка при обновлении на сервере.")
            print("ОШИБКА (Смотри ниже):")
            print(err)
            print("Возможно репозиторий приватный и серверу нужен SSH ключ в GitHub, чтобы pull-ить без пароля.")
        
        client.close()
            
    except Exception as e:
        print(f"❌ Ошибка подключения к VPS: {e}")

if __name__ == '__main__':
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    main()
