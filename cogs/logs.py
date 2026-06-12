import discord
from discord.ext import commands, tasks
import logging
import os
import json
import datetime
import aiohttp
from config import COLOR_SUCCESS, COLOR_ERROR, TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID
from utils.db import db


class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_backup_loop.start()

    def cog_unload(self):
        self.db_backup_loop.cancel()

    @tasks.loop(hours=24)
    async def db_backup_loop(self):
        try:
            # Получаем все таблицы из БД
            tables = ['users', 'global_settings', 'profile_settings', 'user_achievements', 'streamer_activity']
            backup_data = {}
            
            if db.pool is None:
                logging.warning("Database pool is not ready for backup.")
                return

            async with db.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    for table in tables:
                        try:
                            await cur.execute(f"SELECT * FROM {table}")
                            rows = await cur.fetchall()
                            # Конвертируем datetime в строку для JSON
                            for row in rows:
                                for k, v in row.items():
                                    if isinstance(v, (datetime.datetime, datetime.date)):
                                        row[k] = v.isoformat()
                            backup_data[table] = rows
                        except Exception as e:
                            logging.error(f"Error fetching table {table}: {e}")

            file_path = "mriamys_backup.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=4)

            # Отправляем в Telegram
            if TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_ID:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
                data = aiohttp.FormData()
                data.add_field('chat_id', str(TELEGRAM_ADMIN_ID))
                data.add_field('document', open(file_path, 'rb'), filename=f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json")
                data.add_field('caption', "💾 Автоматический бэкап базы данных (MySQL -> JSON)")
                
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.post(url, data=data) as response:
                            if response.status == 200:
                                logging.info("DB backup sent to Telegram successfully.")
                            else:
                                resp_text = await response.text()
                                logging.error(f"Failed to send DB to Telegram: {response.status} - {resp_text}")
                    except Exception as e:
                        logging.error(f"Error sending DB backup to Telegram: {e}")

            # Отправляем в логи Discord
            for guild in self.bot.guilds:
                log_channel = await self.get_log_channel(guild)
                if log_channel:
                    embed = discord.Embed(
                        title="💾 Автоматический Бэкап Базы Данных",
                        description="Ежедневная копия таблиц MySQL.\n*Сохраните этот файл, если хотите перенести бота на другой сервер!*",
                        color=0x2ECC71,
                        timestamp=discord.utils.utcnow(),
                    )
                    try:
                        await log_channel.send(embed=embed, file=discord.File(file_path))
                    except Exception as e:
                        logging.error(f"Error sending DB backup to Discord: {e}")
                        
        except Exception as e:
            logging.error(f"Error during DB Backup: {e}")

    @db_backup_loop.before_loop
    async def before_db_backup(self):
        await self.bot.wait_until_ready()

    async def get_log_channel(self, guild):
        for channel in guild.text_channels:
            if "логи" in channel.name.lower():
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
            timestamp=discord.utils.utcnow(),
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
            color=0xFEE75C,  # Yellow
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Было:", value=before.content[:1000] or "Пусто", inline=False
        )
        embed.add_field(
            name="Стало:", value=after.content[:1000] or "Пусто", inline=False
        )
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
                timestamp=discord.utils.utcnow(),
            )
            await log_channel.send(embed=embed)

        # Выход из канала
        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(
                title="🚪 Выход из голосового канала",
                description=f"{member.mention} ({member}) вышел из **{before.channel.name}**",
                color=COLOR_ERROR,
                timestamp=discord.utils.utcnow(),
            )
            await log_channel.send(embed=embed)

        # Перемещение между каналами
        elif (
            before.channel is not None
            and after.channel is not None
            and before.channel != after.channel
        ):
            embed = discord.Embed(
                title="🔄 Перемещение",
                description=f"{member.mention} ({member}) перешел из **{before.channel.name}** в **{after.channel.name}**",
                color=0x3498DB,  # Blue
                timestamp=discord.utils.utcnow(),
            )
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        log_channel = await self.get_log_channel(member.guild)
        if not log_channel:
            return

        embed = discord.Embed(
            title="📤 Участник покинул сервер",
            description=f"**Пользователь:** {member.mention} ({member})\n**ID:** {member.id}",
            color=0xE74C3C,  # Red
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await log_channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Logger(bot))
