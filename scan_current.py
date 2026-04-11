import discord
import asyncio
import sys
import os
from dotenv import load_dotenv

# Handling encoding for Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class MyClient(discord.Client):
    async def on_ready(self):
        print(f"--- SERVER ANALYSIS START ---")
        print(f"Logged in as: {self.user}")
        for guild in self.guilds:
            print(f"\nGuild Name: {guild.name} (ID: {guild.id})")
            print(f"Member Count: {guild.member_count}")
            
            print("\nCategories & Channels:")
            for category in guild.categories:
                print(f"[CATEGORY] {category.name}")
                for channel in category.channels:
                    print(f"  - [{type(channel).__name__}] {channel.name}")
            
            # Orphan channels
            orphans = [c for c in guild.channels if c.category is None]
            if orphans:
                print("\n[ORPHAN CHANNELS]")
                for channel in orphans:
                    print(f"  - [{type(channel).__name__}] {channel.name}")

            print("\nRoles:")
            for role in guild.roles:
                if not role.is_default():
                    print(f"  - {role.name} (ID: {role.id})")
        print(f"\n--- SERVER ANALYSIS END ---")
        await self.close()

intents = discord.Intents.default()
client = MyClient(intents=intents)
client.run(TOKEN)
