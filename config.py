import os
from dotenv import load_dotenv

load_dotenv()

# Discord
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "!"

# MySQL Database
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "mriamys")
DB_PASS = os.getenv("DB_PASS", "password")
DB_NAME = os.getenv("DB_NAME", "mriamys_bot")

# Цвета для красивых Embed
COLOR_MAIN = 0x2b2d31  # Цвет фона дискорда для бесшовных Embed
COLOR_SUCCESS = 0x57F287
COLOR_ERROR = 0xED4245
