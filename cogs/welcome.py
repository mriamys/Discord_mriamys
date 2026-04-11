import discord
from discord.ext import commands
import io
import logging
from config import COLOR_SUCCESS
from utils.images import generate_welcome_card

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        logging.info(f"New member joined: {member.name}")
        # Ищем канал для приветствия
        channel = member.guild.system_channel
        if not channel:
            # Пытаемся найти канал по названию (привет, welcome, встреча)
            for ch in member.guild.text_channels:
                ch_name = ch.name.lower()
                if 'привет' in ch_name or 'welcome' in ch_name or 'встреча' in ch_name:
                    channel = ch
                    break
                    
        if channel and channel.permissions_for(member.guild.me).send_messages:
            try:
                # Генерируем картинку
                image_bytes = await generate_welcome_card(member)
                if image_bytes:
                    fp = io.BytesIO(image_bytes)
                    file = discord.File(fp, filename="welcome.png")
                    
                    embed = discord.Embed(
                        title="👋 Новый участник!",
                        description=f"Добро пожаловать на сервер, {member.mention}! 🎉\nМы рады тебя видеть. Чувствуй себя как дома!",
                        color=COLOR_SUCCESS
                    )
                    embed.set_image(url="attachment://welcome.png")
                    await channel.send(content=member.mention, embed=embed, file=file)
            except Exception as e:
                logging.error(f"Error sending welcome message: {e}")

async def setup(bot):
    await bot.add_cog(Welcome(bot))
