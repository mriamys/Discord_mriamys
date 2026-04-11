import discord
from discord.ext import commands, tasks
import logging
import os
from config import COLOR_SUCCESS, COLOR_ERROR

class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_backup_loop.start()

    def cog_unload(self):
        self.db_backup_loop.cancel()

    @tasks.loop(hours=24)
    async def db_backup_loop(self):
        try:
            db_path = "data/mriamys.db"
            if not os.path.exists(db_path):
                return
            
            for guild in self.bot.guilds:
                log_channel = await self.get_log_channel(guild)
                if log_channel:
                    embed = discord.Embed(
                        title="💾 Автоматический Бэкап Базы Данных",
                        description="Ежедневная копия файла `mriamys.db` (Уровни, валюта, настройки).\n*Сохраните этот файл, если хотите перенести бота на другой сервер!*",
                        color=0x2ecc71,
                        timestamp=discord.utils.utcnow()
                    )
                    await log_channel.send(embed=embed, file=discord.File(db_path))
        except Exception as e:
            logging.error(f"Error during DB Backup: {e}")

    @db_backup_loop.before_loop
    async def before_db_backup(self):
        await self.bot.wait_until_ready()

    async def get_log_channel(self, guild):
        for channel in guild.text_channels:
            if 'логи' in channel.name.lower():
                return channel
        return None

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return
            
        log_channel = await self.get_log_channel(message.guild)
        if not log_channel:
            return
            
        embed = discord.Embed(
            title="🗑️ Сообщение удалено",
            description=f"**Автор:** {message.author.mention} ({message.author})\n**Канал:** {message.channel.mention}\n\n**Содержание:**\n{message.content or 'Без текста (файлы/стикеры)'}",
            color=COLOR_ERROR,
            timestamp=discord.utils.utcnow()
        )
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content:
            return

        log_channel = await self.get_log_channel(before.guild)
        if not log_channel:
            return

        embed = discord.Embed(
            title="✏️ Сообщение изменено",
            description=f"**Автор:** {before.author.mention} ({before.author})\n**Канал:** {before.channel.mention}\n**Ссылка:** [Перейти к сообщению]({after.jump_url})",
            color=0xFEE75C, # Yellow
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Было:", value=before.content[:1000] or "Пусто", inline=False)
        embed.add_field(name="Стало:", value=after.content[:1000] or "Пусто", inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        log_channel = await self.get_log_channel(member.guild)
        if not log_channel:
            return

        # Вход в канал
        if before.channel is None and after.channel is not None:
            embed = discord.Embed(
                title="🎤 Вход в голосовой канал",
                description=f"{member.mention} ({member}) зашел в **{after.channel.name}**",
                color=COLOR_SUCCESS,
                timestamp=discord.utils.utcnow()
            )
            await log_channel.send(embed=embed)
            
        # Выход из канала
        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(
                title="🚪 Выход из голосового канала",
                description=f"{member.mention} ({member}) вышел из **{before.channel.name}**",
                color=COLOR_ERROR,
                timestamp=discord.utils.utcnow()
            )
            await log_channel.send(embed=embed)
            
        # Перемещение между каналами
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            embed = discord.Embed(
                title="🔄 Перемещение",
                description=f"{member.mention} ({member}) перешел из **{before.channel.name}** в **{after.channel.name}**",
                color=0x3498DB, # Blue
                timestamp=discord.utils.utcnow()
            )
            await log_channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Logger(bot))
