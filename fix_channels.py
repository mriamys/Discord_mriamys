import discord
import asyncio
from config import TOKEN
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from cogs.roles import GAME_OPTIONS, DEV_OPTIONS

class FixerClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())

    async def on_ready(self):
        print(f"Logged in as {self.user}. Starting fix...")
        for guild in self.guilds:
            print(f"Fixing guild: {guild.name}")
            
            # Fix Game Categories
            for game, emoji in GAME_OPTIONS.items():
                role = discord.utils.get(guild.roles, name=game)
                category = None
                for cat in guild.categories:
                    if game.upper() in cat.name.upper():
                        category = cat
                        break
                        
                if category and role:
                    print(f"Fixing game category: {category.name}")
                    try:
                        await category.set_permissions(guild.default_role, read_messages=False, connect=False)
                        await category.set_permissions(role, read_messages=True, connect=True)
                    except Exception as e:
                        print(f"Error fixing {category.name}: {e}")

            # Fix Dev Category
            cat_name = "💻┃ПРОГРАММИРОВАНИЕ"
            category = discord.utils.get(guild.categories, name=cat_name)
            if category:
                print("Fixing IT category...")
                try:
                    await category.set_permissions(guild.default_role, read_messages=False, connect=False)
                except Exception as e:
                    print(f"Error hiding IT category: {e}")
                
                # Each dev role should see the category
                for dev in DEV_OPTIONS.keys():
                    role = discord.utils.get(guild.roles, name=f"{dev} Coder")
                    if role:
                        try:
                            await category.set_permissions(role, read_messages=True, connect=True)
                        except Exception as e:
                            print(f"Error setting IT category for {role.name}: {e}")
                            
                    # Each dev language chat
                    clean_name = dev.lower().replace("++", "pp").replace("#", "sharp")
                    chan_name = f"💬┃{clean_name}-chat"
                    chan = discord.utils.get(guild.text_channels, name=chan_name)
                    if chan and role:
                        print(f"Fixing dev chat: {chan.name}")
                        try:
                            await chan.set_permissions(guild.default_role, read_messages=False)
                            await chan.set_permissions(role, read_messages=True)
                        except Exception as e:
                            print(f"Error fixing {chan.name}: {e}")
                            
        print("Done!")
        await self.close()

if __name__ == "__main__":
    client = FixerClient()
    client.run(TOKEN)
