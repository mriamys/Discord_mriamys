import discord
from discord.ext import commands
import io
import os
import logging
from config import COLOR_SUCCESS
from utils.images import generate_welcome_card

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_channel_id = os.getenv("WELCOME_CHANNEL_ID")

    async def get_welcome_channel(self, guild: discord.Guild):
        # 1. Приоритет — явный ID из .env
        if self.welcome_channel_id and self.welcome_channel_id.strip().isdigit():
            ch = guild.get_channel(int(self.welcome_channel_id))
            if ch:
                return ch

        # 2. Системный канал Discord
        if guild.system_channel:
            return guild.system_channel

        # 3. Поиск по ключевым словам в названии
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
            logging.warning(f"Welcome channel not found for guild {member.guild.name}")
            return

        if not channel.permissions_for(member.guild.me).send_messages:
            logging.warning(f"No permission to send in welcome channel #{channel.name}")
            return

        try:
            image_bytes = await generate_welcome_card(member)
            if image_bytes:
                fp = io.BytesIO(image_bytes)
                file = discord.File(fp, filename="welcome.png")

                embed = discord.Embed(
                    title="👋 Новый участник!",
                    description=(
                        f"Добро пожаловать на сервер, {member.mention}! 🎉\n"
                        f"Мы рады тебя видеть. Чувствуй себя как дома!\n\n"
                        f"**Обязательно выбери свои роли в канале с выдачей ролей**, "
                        f"чтобы получить доступ к нужным комнатам!"
                    ),
                    color=COLOR_SUCCESS
                )
                embed.set_image(url="attachment://welcome.png")
                await channel.send(content=member.mention, embed=embed, file=file)
                logging.info(f"Welcome message sent to #{channel.name} for {member.name}")
        except Exception as e:
            logging.error(f"Error sending welcome message: {e}")
    @discord.app_commands.command(name="testwelcome", description="Проверить приветственное сообщение")
    @discord.app_commands.default_permissions(administrator=True)
    async def test_welcome(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = await self.get_welcome_channel(interaction.guild)
        if not channel:
            await interaction.followup.send("❌ Канал приветствия не найден! Заполни `WELCOME_CHANNEL_ID` в `.env`", ephemeral=True)
            return
        try:
            image_bytes = await generate_welcome_card(interaction.user)
            if image_bytes:
                fp = io.BytesIO(image_bytes)
                file = discord.File(fp, filename="welcome.png")
                embed = discord.Embed(
                    title="👋 Новый участник!",
                    description=(
                        f"Добро пожаловать на сервер, {interaction.user.mention}! 🎉\n"
                        f"Мы рады тебя видеть. Чувствуй себя как дома!\n\n"
                        f"**Обязательно выбери свои роли в канале с выдачей ролей**, "
                        f"чтобы получить доступ к нужным комнатам!"
                    ),
                    color=COLOR_SUCCESS
                )
                embed.set_image(url="attachment://welcome.png")
                await channel.send(content=interaction.user.mention, embed=embed, file=file)
                await interaction.followup.send(f"✅ Тест отправлен в канал {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка: `{e}`", ephemeral=True)
            logging.error(f"Test welcome error: {e}")

async def setup(bot):
    await bot.add_cog(Welcome(bot))
