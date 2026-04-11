import discord
import asyncio
import os
import sys
from dotenv import load_dotenv

# Фикс кодировки для Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Конфигурация новых рангов
RANKS = [
    (0, "[🌫️] Кринж", 0x95a5a6),
    (5, "[👞] Попуск", 0x7f8c8d),
    (10, "[👶] Шкет", 0xbdc3c7),
    (15, "[🍺] Подпивас", 0x99aab5),
    (20, "[🧔] Скуф", 0x7d6608),
    (25, "[🧘] На чилле", 0x27ae60),
    (30, "[🕺] Флексер", 0x2ecc71),
    (35, "[🕶️] Нормис", 0x3498db),
    (40, "[🔥] Тот самый", 0xe67e22),
    (45, "[👌] Мегахорош", 0xe74c3c),
    (50, "[🗿] Гигачад", 0x1abc9c),
    (55, "[⚡] Сигма", 0x9b59b6),
    (60, "[🧚] Альтушка", 0xff69b4),
    (65, "[👵] Олд", 0x34495e),
    (70, "[🌟] Легенда", 0xf1c40f),
    (75, "[🧔‍♂️] Гранд-Скуф", 0x9c640c),
    (80, "[👑] Папич", 0x111111),
    (90, "[🏋️] Босс качалки", 0x206694),
    (100, "[🌌] Абсолют", 0x71368a)
]

SPECIAL_ROLES = [
    ("[💻] Программист", 0x00ff00),
    ("[🎥] Стример", 0x6441a5),
    ("[🎞️] Ютубер", 0xff0000),
    ("[📱] Тик-токер", 0x010101)
]

ROLES_TO_DELETE = [
    "УЕБИЩЕ", "новичок", "молодчинка", "умный", "хороший", 
    "Maki.gg", "Logger", "YAGPDB.xyz", "MEE6", "JuniperBot"
]

class CleanupClient(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user}')
        guild = self.guilds[0] # Assume one guild
        print(f'Cleaning up guild: {guild.name}')

        # 1. DELETE TRASH ROLES
        for role in guild.roles:
            if role.name in ROLES_TO_DELETE:
                try:
                    await role.delete()
                    print(f'Deleted role: {role.name}')
                except:
                    print(f'Could not delete role: {role.name} (maybe system/managed)')

        # 2. RENAME STAFF ROLES
        staff_mapping = {
            "Президент": "[👑] Владелец",
            "админ": "[🛡️] Админ",
            "модератор": "[🛠️] Модер"
        }
        for role in guild.roles:
            old_name = role.name
            if old_name in staff_mapping:
                new_name = staff_mapping[old_name]
                try:
                    await role.edit(name=new_name, hoist=True)
                    print(f'Renamed staff role: {old_name} -> {new_name}')
                except Exception as e:
                    print(f'Could not rename role {old_name}: {e}')

        # 3. CREATE NEW MEME RANKS
        existing_role_names = [r.name for r in guild.roles]
        for lvl, name, color in RANKS:
            if name not in existing_role_names:
                new_role = await guild.create_role(
                    name=name, 
                    colour=discord.Colour(color), 
                    hoist=True,
                    reason="Meme Leveling System"
                )
                print(f'Created rank: {name}')

        # 4. CREATE SPECIAL ROLES
        for name, color in SPECIAL_ROLES:
            if name not in existing_role_names:
                await guild.create_role(
                    name=name,
                    colour=discord.Colour(color),
                    hoist=True,
                    reason="Special Roles"
                )
                print(f'Created special role: {name}')

        # 5. CLEANUP CHANNELS (TRASH)
        # Delete among us extra categories
        for category in guild.categories:
            if "AMONG US #" in category.name and category.name != "🔪┃AMONG US #1":
                for channel in category.channels:
                    await channel.delete()
                await category.delete()
                print(f'Deleted extra category: {category.name}')

        print('Cleanup complete!')
        await self.close()

client = CleanupClient(intents=discord.Intents.all())
client.run(TOKEN)
