import discord
import asyncio
import os
from dotenv import load_dotenv

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import TOKEN

GAME_OPTIONS = {
    "CS2": "🎯", "Rust": "🏕️", "Valorant": "🎭", "Apex Legends": "🔫",
    "Fortnite": "⛏️", "GTA V": "💰", "GTA SA": "🚗", "Rocket League": "🏎️",
    "Among Us": "🔪", "Euro Truck": "🚛", "Dota 2": "⚔️", "Minecraft": "🪚",
    "League of Legends": "🧙‍♂️", "PUBG": "🍳"
}

DEV_OPTIONS = {
    "Python": "🐍", "Java": "☕", "JavaScript": "📜",
    "CSS": "🎨", "HTML": "🌐", "C++": "⚙️", "C#": "💠"
}

MEME_RANKS = {
    0: "[🌫️] Кринж", 5: "[👞] Попуск", 10: "[👶] Шкет", 15: "[🍺] Подпивас",
    20: "[🧔] Скуф", 25: "[🧘] На чилле", 30: "[🕺] Флексер", 35: "[🕶️] Нормис",
    40: "[🔥] Тот самый", 45: "[👌] Мегахорош", 50: "[🗿] Гигачад",
    55: "[⚡] Сигма", 60: "[🧚] Альтушка", 65: "[👵] Олд", 70: "[🌟] Легенда",
    75: "[🧔‍♂️] Гранд-Скуф", 80: "[👑] Папич", 90: "[🏋️] Босс качалки", 100: "[🌌] Абсолют"
}

class HoistClient(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user}')
        
        target_role_names = set()
        for game in GAME_OPTIONS.keys():
            target_role_names.add(game)
        for dev in DEV_OPTIONS.keys():
            target_role_names.add(f"{dev} Coder")
        for rank in MEME_RANKS.values():
            target_role_names.add(rank)
            
        count = 0
        for guild in self.guilds:
            for role in guild.roles:
                if role.name in target_role_names and not role.hoist:
                    try:
                        await role.edit(hoist=True)
                        print(f"Hoisted role: {role.name}")
                        count += 1
                        await asyncio.sleep(1) # rate limit prevention
                    except Exception as e:
                        print(f"Failed to hoist role {role.name}: {e}")
                        
        print(f"Finished! Updated {count} roles to hoisted. Exiting...")
        await self.close()

if __name__ == "__main__":
    intents = discord.Intents.default()
    client = HoistClient(intents=intents)
    client.run(TOKEN)
