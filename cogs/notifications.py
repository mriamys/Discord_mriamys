import discord
from discord.ext import commands
import aiohttp
import logging
from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_ADMIN_ID,
    ADMIN_DISCORD_ID,
    COLOR_SUCCESS,
)


class Notifications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        # Игнорируем ботов и самого себя (админа)
        if member.bot or member.id == ADMIN_DISCORD_ID:
            return

        # Проверяем, зашел ли пользователь в канал (был ли он в канале до этого)
        if before.channel is None and after.channel is not None:
            logging.info(f"User {member} joined voice channel {after.channel.name}")

            # Проверяем, находится ли админ в этом же канале
            guild = member.guild
            admin = guild.get_member(ADMIN_DISCORD_ID)

            # Если админа нет в канале (или он вообще не в войсе)
            if (
                admin is None
                or admin.voice is None
                or admin.voice.channel != after.channel
            ):
                await self.send_telegram_notification(
                    member, after.channel, event_type="join"
                )

        # Проверяем, вышел ли пользователь из канала (был ли он в канале и теперь его нет)
        elif before.channel is not None and after.channel is None:
            logging.info(f"User {member} left voice channel {before.channel.name}")

            # Проверяем, находился ли админ в этом же канале
            guild = member.guild
            admin = guild.get_member(ADMIN_DISCORD_ID)

            # Если админа нет в канале (или он вообще не в войсе)
            if (
                admin is None
                or admin.voice is None
                or admin.voice.channel != before.channel
            ):
                await self.send_telegram_notification(
                    member, before.channel, event_type="leave"
                )

    async def send_telegram_notification(
        self,
        member: discord.Member,
        channel: discord.VoiceChannel,
        event_type: str = "join",
    ) -> None:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_ID:
            logging.warning("Telegram credentials not set in config/env")
            return

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        # Формируем сообщение в зависимости от события
        if event_type == "join":
            title = "🔔 <b>Кто-то зашёл в войс!</b>"
        else:
            title = "🔕 <b>Кто-то вышел из войса!</b>"

        text = (
            f"{title}\n\n"
            f"👤 <b>Пользователь:</b> {member.display_name} ({member})\n"
            f"🎤 <b>Канал:</b> {channel.name}\n"
            f"🌐 <b>Сервер:</b> {member.guild.name}\n"
            f"👥 <b>Всего в канале:</b> {len(channel.members)}"
        )

        async with aiohttp.ClientSession() as session:
            payload = {"chat_id": TELEGRAM_ADMIN_ID, "text": text, "parse_mode": "HTML"}
            try:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logging.info(f"Telegram notification sent for {member}")
                    else:
                        resp_text = await response.text()
                        logging.error(
                            f"Failed to send Telegram notification: {response.status} - {resp_text}"
                        )
            except Exception as e:
                logging.error(f"Error sending Telegram notification: {e}")


async def setup(bot):
    await bot.add_cog(Notifications(bot))
