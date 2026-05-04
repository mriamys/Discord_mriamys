# Discord Mriamys Bot 🚀

Ультимативный мемный бот для Discord сервера Mriamys. 
Включает в себя динамические комнаты, систему VibeКоинов, ленивый Spotify плеер, магазин рофлов и уведомления в Telegram.

## Основные функции
* 🎵 **Музыка**: Плеер с поддержкой YouTube и Spotify.
* 💰 **Экономика**: VibeКоины, магазин ролей и предметов.
* 📈 **Уровни**: Система опыта и уровней с кастомными карточками профиля.
* 🎭 **Роли**: Панель выбора ролей и авто-выдача.
* 🔊 **Динамические комнаты**: Автоматическое создание приваток.
* 🔔 **Уведомления**: Отправка уведомлений в Telegram (через TikTok бота), когда кто-то заходит в голосовой канал.

## Стек технологий
* `python 3+` (discord.py)
* `aiomysql` (База данных)
* `yt-dlp` (Музыка)
* `easy-pil` (Генерация профильных карточек)
* `aiohttp` (API уведомления)

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

# MySQL
DB_HOST=localhost
DB_USER=mriamys
DB_PASS=твой_пароль
DB_NAME=mriamys_bot

# Telegram Notifications
TELEGRAM_BOT_TOKEN=токен_бота_из_botfather
TELEGRAM_ADMIN_ID=твой_телеграм_id
ADMIN_DISCORD_ID=твой_дискорд_id
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
