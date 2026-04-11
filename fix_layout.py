import discord
import asyncio
import sys
import os
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class MyClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as: {self.user}")
        guild = self.guilds[0] # Берем первый сервер

        # Ищем или создаем категорию ETS2
        ets_category = discord.utils.get(guild.categories, name="🚛┃EURO TRUCK SIMULATOR 2")
        if not ets_category:
            print("Создаем категорию 🚛┃EURO TRUCK SIMULATOR 2")
            ets_category = await guild.create_category("🚛┃EURO TRUCK SIMULATOR 2")
        else:
            print("Категория 🚛┃EURO TRUCK SIMULATOR 2 уже существует.")

        # Создаем текстовый чат, если его нет
        ets_text = discord.utils.get(guild.text_channels, name="💬┃ets2-chat")
        if not ets_text:
            print("Создаем текстовый канал 💬┃ets2-chat")
            await guild.create_text_channel("💬┃ets2-chat", category=ets_category)
        else:
            if ets_text.category != ets_category:
                print("Переносим текстовый канал 💬┃ets2-chat в категорию")
                await ets_text.edit(category=ets_category)

        # Переносим голосовой Euro Track
        ets_voice = discord.utils.get(guild.voice_channels, name="🚛┃EURO TRACK")
        if ets_voice:
            if ets_voice.category != ets_category:
                print("Переносим голосовой канал 🚛┃EURO TRACK в нужную категорию")
                await ets_voice.edit(category=ets_category)
        else:
            # Если почему-то нет, создадим 
            print("Создаем голосовой канал 🚛┃EURO TRACK")
            await guild.create_voice_channel("🚛┃EURO TRACK", category=ets_category)

        print("Фикс структуры завершен!")
        await self.close()

intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.message_content = True
client = MyClient(intents=intents)
client.run(TOKEN)
