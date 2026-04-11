import discord
import asyncio
import os
from config import TOKEN

class InitShopClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        guild = list(self.guilds)[0] # Берем первый (и скорее всего единственный) сервер
        
        # Создаем категорию или берем существующую
        category = discord.utils.get(guild.categories, name="🛒┃Магазин")
        if not category:
            category = await guild.create_category("🛒┃Магазин")
            print("Category created.")
            
        # Создаем текстовый канал магазина
        shop_channel = discord.utils.get(guild.text_channels, name="🛒┃магазин")
        if not shop_channel:
            shop_channel = await guild.create_text_channel("🛒┃магазин", category=category)
            print("Shop channel created.")
        else:
            print("Shop channel already exists.")
            
        await self.close()

if __name__ == "__main__":
    client = InitShopClient()
    client.run(TOKEN)
