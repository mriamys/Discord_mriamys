import discord
from discord.ext import commands
import os
import asyncio
import logging
import sys
from config import TOKEN, PREFIX
from utils.db import db

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Фикс кодировки для Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

class MriamysBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=None)

    async def setup_hook(self):
        logging.info("Initializing Database...")
        await db.connect()
        await db.init_tables()
        
        logging.info("Loading Cogs...")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logging.info(f"Loaded extension: {filename}")
                except Exception as e:
                    logging.error(f"Failed to load extension {filename}: {e}")
                    
        # Добавляем Persistent Views
        try:
            from cogs.shop import ShopView
            from cogs.leveling import LevelUpView
            from cogs.casino import CasinoView
            from cogs.cases import CaseView
            from cogs.duels import DuelRoomView
            from cogs.quiz import QuizRoomView

            self.add_view(ShopView())
            self.add_view(LevelUpView())
            self.add_view(CasinoView())
            self.add_view(CaseView())
            self.add_view(DuelRoomView())
            self.add_view(QuizRoomView(self))
            logging.info("Registered all Persistent Views")
        except Exception as e:
            logging.error(f"Failed to register persistent views: {e}")


            
        try:
            synced = await self.tree.sync()
            logging.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logging.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        logging.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logging.info("Bot is ready for VibeCoding!")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
            
        embed = discord.Embed(title="❌ Ошибка", color=discord.Color.red())
        
        if isinstance(error, commands.MissingPermissions):
            embed.description = "У вас нет подходящих прав (роли) для выполнения этой команды!"
        elif isinstance(error, commands.MissingRequiredArgument):
            embed.description = f"Вы пропустили обязательный аргумент: `{error.param.name}`\nНапишите `!help` для подробностей."
        elif isinstance(error, commands.CommandOnCooldown):
            embed.description = f"Команда перегрелась! Подождите {error.retry_after:.1f} сек."
        else:
            embed.description = f"Произошла непредвиденная ошибка: `{type(error).__name__}`"
            logging.error(f"Ignored exception in command {ctx.command}: {error}")
            
        try:
            await ctx.send(embed=embed)
        except Exception:
            pass

bot = MriamysBot()

if __name__ == '__main__':
    try:
        bot.run(TOKEN)
    except Exception as e:
        logging.error(f"Error running bot: {e}")
