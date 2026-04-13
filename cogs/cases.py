import discord
from discord.ext import commands
from discord.ui import View, Button
from utils.db import db
from config import COLOR_MAIN
import asyncio
import random
import logging

class CaseView(View):
    def __init__(self, user_id: str):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="Открыть Кейс (1000 🪙)", style=discord.ButtonStyle.success, emoji="📦")
    async def btn_open(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("Это не твой кейс!", ephemeral=True)
            return

        user_data = await db.get_user(self.user_id)
        balance = user_data.get('vibecoins', 0)
        price = 1000

        if balance < price:
            await interaction.response.send_message(f"❌ Не хватает **VibeКоинов**! У тебя {balance}/{price} 🪙", ephemeral=True)
            return

        # Снимаем деньги
        new_balance = balance - price
        cases_opened = user_data.get('cases_opened', 0) + 1
        await db.update_user(self.user_id, vibecoins=new_balance, cases_opened=cases_opened)
        
        interaction.client.dispatch("case_opened", interaction.user, cases_opened)

        win_amount = random.randint(100, 5000)

        # Отправляем начальное сообщение с анимацией
        embed = discord.Embed(title="📦 Открытие Vibe Кейса...", description="[ 🎰 ] КРУТИМ РУЛЕТКУ [ 🎰 ]", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed)
        
        # Анимация "цифрового потока"
        steps = [random.randint(100, 5000) for _ in range(3)]
        
        for step_val in steps:
            await asyncio.sleep(0.8)
            embed.description = f"**[ {step_val} 🪙 ]**"
            try:
                await interaction.edit_original_response(embed=embed)
            except discord.HTTPException:
                pass

        await asyncio.sleep(1)

        # Финальный результат
        embed.title = "📦 Vibe Кейс открыт!"
        if win_amount > price:
            embed.color = discord.Color.green()
            embed.description = f"🎉 ОКУП! Выпало: **{win_amount} 🪙**\nТекущий баланс: **{new_balance + win_amount} 🪙**"
        else:
            embed.color = discord.Color.red()
            embed.description = f"📉 Минус... Выпало: **{win_amount} 🪙**\nТекущий баланс: **{new_balance + win_amount} 🪙**"

        await db.update_user(self.user_id, vibecoins=new_balance + win_amount)
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label="Выйти", style=discord.ButtonStyle.danger, emoji="🚪")
    async def btn_close(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Только владелец комнаты или админ может её закрыть.", ephemeral=True)
            return

        await interaction.response.send_message("🚪 Закрываю комнату...")
        await asyncio.sleep(2)
        try:
            await interaction.channel.delete(reason="Игрок вышел из комнаты кейсов")
        except:
            pass

class Cases(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_create_vibe_case_room(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        channel_name = f"📦┃кейс-{interaction.user.name[:10]}"
        existing = discord.utils.get(guild.channels, name=channel_name.lower())
        if existing:
            await interaction.followup.send(f"У тебя уже открыта комната: {existing.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user:   discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me:           discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        
        try:
            channel = await guild.create_text_channel(
                channel_name,
                overwrites=overwrites,
                category=interaction.channel.category,
                topic=f"Личная комната для открытия Vibe Кейсов 📦"
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ У бота нет прав для создания приватного канала.", ephemeral=True)
            return

        await interaction.followup.send(f"✅ Комната создана: {channel.mention}", ephemeral=True)
        
        embed = discord.Embed(
            title="📦 Vibe Кейсы",
            description=(
                "Цена одного кейса: **1000 🪙**\n"
                "Выпасть может случайная сумма от **100 🪙** до **5000 🪙**!\n\n"
                "Жми кнопку ниже, чтобы попытать удачу. Когда надоест - жми Выйти."
            ),
            color=COLOR_MAIN
        )
        embed.set_image(url="https://media.giphy.com/media/26ufncG0MtwzYulkk/giphy.gif")
        
        await channel.send(content=interaction.user.mention, embed=embed, view=CaseView(str(interaction.user.id)))

        # Автоудаление комнаты через час
        async def _delete_channel():
            await asyncio.sleep(3600)
            try:
                await channel.delete(reason="Время комнаты вышло")
            except:
                pass
        self.bot.loop.create_task(_delete_channel())

async def setup(bot):
    await bot.add_cog(Cases(bot))
