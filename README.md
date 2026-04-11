# Discord Mriamys Bot 🚀

Ультимативный мемный бот для Discord сервера Mriamys. 
Включает в себя динамические комнаты, систему VibeКоинов, ленивый Spotify плеер и магазин рофлов.

## Стек технологий
* `python 3+` (discord.py)
* `aiomysql` (База данных)
* `yt-dlp` (Музыка)
* `easy-pil` (Генерация профильных карточек)

## Запуск на VPS (Ubuntu)

1. Клонируйте репозиторий:
```bash
git clone https://github.com/mriamys/Discord_mriamys.git
cd Discord_mriamys
```

2. Установите зависимости (нужен ffmpeg для музыки):
```bash
sudo apt update
sudo apt install ffmpeg python3-pip -y
pip install -r requirements.txt
```

3. Настройка `.env`:
Создайте файл `.env` на сервере:
```
DISCORD_TOKEN=твой_токен
DB_HOST=localhost
DB_USER=mriamys
DB_PASS=твой_пароль
DB_NAME=mriamys_bot
```

4. Инициализация MySQL:
```sql
CREATE DATABASE mriamys_bot;
CREATE USER 'mriamys'@'localhost' IDENTIFIED BY 'твой_пароль';
GRANT ALL PRIVILEGES ON mriamys_bot.* TO 'mriamys'@'localhost';
FLUSH PRIVILEGES;
```

5. Деплой через SystemD:
```bash
sudo cp mriamys.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mriamys
sudo systemctl start mriamys
```
