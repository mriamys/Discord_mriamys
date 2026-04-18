import discord
from discord.ext import commands
import io
import logging
from config import COLOR_SUCCESS
from utils.images import generate_welcome_card

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_welcome_channel(self, guild: discord.Guild):
        # 1. Сначала проверяем системный канал Discord
        if guild.system_channel:
            return guild.system_channel

        # 2. Иначе ищем по ключевым словам в названии
        keywords = ['приветик', 'привет', 'welcome', 'встреча']
        for ch in guild.text_channels:
            ch_name = ch.name.lower()
            if any(k in ch_name for k in keywords):
                if ch.permissions_for(guild.me).send_messages:
                    return ch
        return None

    @commands.Cog.listener()
    async def on_member_join(self, member):
        logging.info(f"New member joined: {member.name}")

        channel = await self.get_welcome_channel(member.guild)
        if not channel:
            return

        try:
            image_bytes = await generate_welcome_card(member)
            
            # Находим канал выдачи ролей
            roles_channel = discord.utils.get(member.guild.text_channels, name="🎭┃выдача-ролей")
            roles_mention = roles_channel.mention if roles_channel else "канале с выдачей ролей"

            if image_bytes:
                # Фикс: easy-pil возвращает объект, готовый к отправке
                file = discord.File(image_bytes, filename="welcome.png")

                embed = discord.Embed(
                    title="👋 Новый участник!",
                    description=(
                        f"Добро пожаловать на сервер, {member.mention}! 🎉\n"
                        f"Мы рады тебя видеть. Чувствуй себя как дома!\n\n"
                        f"**Обязательно выбери свои роли в {roles_mention}**, "
                        f"чтобы получить доступ к нужным комнатам!"
                    ),
                    color=COLOR_SUCCESS
                )
                embed.set_image(url="attachment://welcome.png")
                await channel.send(content=member.mention, embed=embed, file=file)
                logging.info(f"Welcome message sent to #{channel.name} for {member.name}")
        except Exception as e:
            logging.error(f"Error sending welcome message: {e}")

async def setup(bot):
    await bot.add_cog(Welcome(bot))
