import discord
from discord.ext import commands
from discord.ui import View, Button, UserSelect, Modal, TextInput
from utils.db import db
from config import COLOR_MAIN
import asyncio
import random
import logging

def get_duel_embed():
    return discord.Embed(
        title="⚔️ Дуэльный Клуб",
        description=(
            "Выбери жертву из списка ниже и введи сумму ставки.\n"
            "Если оппонент примет вызов - вы скидываетесь в общий банк и бот кидает кости.\n"
            "Победитель забирает всё!"
        ),
        color=discord.Color.dark_red()
    )

class DuelAcceptView(View):
    def __init__(self, challenger: discord.Member, target: discord.Member, bet: int, room_channel: discord.TextChannel):
        super().__init__(timeout=300) # 5 минут на принятие
        self.challenger = challenger
        self.target = target
        self.bet = bet
        self.room_channel = room_channel

    @discord.ui.button(label="Принять Вызов", style=discord.ButtonStyle.success, emoji="⚔️")
    async def btn_accept(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ Этот вызов не для тебя!", ephemeral=True)
            return

        user_data = await db.get_user(str(self.target.id))
        balance = user_data.get('vibecoins', 0)
        c_data = await db.get_user(str(self.challenger.id))
        c_balance = c_data.get('vibecoins', 0)

        # Перепроверка балансов (вдруг потратили)
        if balance < self.bet:
            await interaction.response.send_message(f"❌ Не хватает **VibeКоинов** для ставки! У тебя {balance}/{self.bet} 🪙", ephemeral=True)
            return
        if c_balance < self.bet:
            await interaction.response.send_message(f"❌ У {self.challenger.display_name} уже нет денег на эту ставку!", ephemeral=True)
            return

        # Снимаем ставки
        await db.update_user(str(self.target.id), vibecoins=balance - self.bet)
        await db.update_user(str(self.challenger.id), vibecoins=c_balance - self.bet)
        
        # Отключаем кнопки
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"⚔️ **Дуэль принята!** Битва начинается...", view=self)

        embed = discord.Embed(title="⚔️ ДУЭЛЬ", description="⏳ Считаем...", color=discord.Color.orange())
        msg = await self.room_channel.send(content=f"{self.challenger.mention} 🆚 {self.target.mention}", embed=embed)

        # Анимация битвы (перебор цифр)
        for _ in range(3):
            await asyncio.sleep(0.4)
            c_roll, t_roll = random.randint(1, 100), random.randint(1, 100)
            embed.description = f"**{self.challenger.display_name}**: 🎲 `[  {c_roll:02d}  ]`\n**{self.target.display_name}**: 🎲 `[  {t_roll:02d}  ]`"
            try:
                await msg.edit(embed=embed)
            except discord.HTTPException:
                pass

        await asyncio.sleep(0.4)
        
        c_final = random.randint(1, 100)
        t_final = random.randint(1, 100)
        while c_final == t_final: # Чтобы не было ничьей
            t_final = random.randint(1, 100)

        winner = self.challenger if c_final > t_final else self.target
        loser = self.target if c_final > t_final else self.challenger

        bank = self.bet * 2

        embed.title = "🏆 ДУЭЛЬ ЗАВЕРШЕНА"
        embed.description = (
            f"**{self.challenger.display_name}**: 🎲 `[  {c_final:02d}  ]`\n"
            f"**{self.target.display_name}**: 🎲 `[  {t_final:02d}  ]`\n\n"
            f"🎉 Победитель: {winner.mention}! Забрал весь банк: **{bank} 🪙**"
        )
        embed.color = discord.Color.green()
        await msg.edit(embed=embed)

        win_data = await db.get_user(str(winner.id))
        duels_won = win_data.get('duels_won', 0) + 1
        await db.update_user(str(winner.id), vibecoins=win_data.get('vibecoins', 0) + bank, duels_won=duels_won)
        
        self.target.client.dispatch("duel_won", winner, duels_won)

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def btn_decline(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target.id and interaction.user.id != self.challenger.id:
            await interaction.response.send_message("❌ Не твоя дуэль!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True
        
        if interaction.user.id == self.target.id:
            await interaction.response.edit_message(content=f"Отменено: {self.target.display_name} испугался.", view=self)
        else:
            await interaction.response.edit_message(content=f"Отменено: {self.challenger.display_name} передумал.", view=self)


class DuelBetModal(Modal):
    def __init__(self, challenger: discord.Member, target: discord.Member, balance: int):
        super().__init__(title=f"Ставка (Баланс: {balance:,})")
        self.challenger = challenger
        self.target = target
        
        self.bet_input = TextInput(
            label=f"Сумма ставки", 
            placeholder="Например: 1000", 
            max_length=10
        )
        self.add_item(self.bet_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet = int(self.bet_input.value)
            if bet <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Введи нормальное число больше 0.", ephemeral=True)
            return

        c_data = await db.get_user(str(self.challenger.id))
        if c_data.get('vibecoins', 0) < bet:
            await interaction.response.send_message(f"❌ У тебя нет **{bet} 🪙**! На балансе: {c_data.get('vibecoins', 0)}", ephemeral=True)
            return
            
        t_data = await db.get_user(str(self.target.id))
        if t_data.get('vibecoins', 0) < bet:
            await interaction.response.send_message(f"❌ У {self.target.display_name} нет **{bet} 🪙**! На балансе: {t_data.get('vibecoins', 0)}", ephemeral=True)
            return

        await interaction.response.send_message(
            f"⚔️ {self.target.mention}, тебя вызывает на дуэль {self.challenger.mention}!\nСтавка: **{bet:,} 🪙**. Победитель забирает всё!",
            view=DuelAcceptView(self.challenger, self.target, bet, interaction.channel)
        )

        # Переотправляем меню вниз
        if interaction.message and interaction.channel.name.startswith("⚔️┃дуэль-"):
            try:
                await interaction.message.delete()
                embed = get_duel_embed()
                await interaction.channel.send(content=self.challenger.mention, embed=embed, view=DuelRoomView(self.challenger.id))
            except:
                pass

class DuelRoomView(View):
    def __init__(self, author_id: int):
        super().__init__(timeout=None)
        self.author_id = author_id

    @discord.ui.select(cls=UserSelect, placeholder="Кого вызываешь на дуэль?", min_values=1, max_values=1)
    async def select_target(self, interaction: discord.Interaction, select: UserSelect):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Только инициатор комнаты может выбирать соперника.", ephemeral=True)
            return

        target = interaction.guild.get_member(select.values[0].id)
        if not target or target.bot:
            await interaction.response.send_message("❌ Нельзя выбрать бота или неизвестного пользователя.", ephemeral=True)
            return

        if target.id == interaction.user.id:
            await interaction.response.send_message("❌ С собой играть скучно. Выбери кого-то другого.", ephemeral=True)
            return

        # Даем права цели в этот канал
        try:
            await interaction.channel.set_permissions(target, read_messages=True, send_messages=True)
        except:
            pass

        user_data = await db.get_user(str(interaction.user.id))
        balance = user_data.get('vibecoins', 0)
        await interaction.response.send_modal(DuelBetModal(interaction.user, target, balance))

    @discord.ui.button(label="Выйти и удалить комнату", style=discord.ButtonStyle.danger, emoji="🚪", row=1)
    async def btn_close(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Только владелец комнаты или админ может её закрыть.", ephemeral=True)
            return

        await interaction.response.send_message("🚪 Закрываю комнату...")
        await asyncio.sleep(2)
        try:
            await interaction.channel.delete(reason="Игрок закрыл дуэльную комнату")
        except:
            pass

class Duels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_create_duel_room(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        channel_name = f"⚔️┃дуэль-{interaction.user.name[:10]}"
        existing = discord.utils.get(guild.channels, name=channel_name.lower())
        if existing:
            await interaction.followup.send(f"У тебя уже открыта комната: {existing.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False, add_reactions=False),
            interaction.user:   discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me:           discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        
        try:
            channel = await guild.create_text_channel(
                channel_name,
                overwrites=overwrites,
                category=interaction.channel.category,
                topic=f"🥷 Публичная арена для дуэлей"
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ У бота нет прав для создания приватного канала.", ephemeral=True)
            return

        await interaction.followup.send(f"✅ Комната создана: {channel.mention}", ephemeral=True)
        
        embed = get_duel_embed()
        
        await channel.send(content=interaction.user.mention, embed=embed, view=DuelRoomView(interaction.user.id))

        async def _delete_channel():
            await asyncio.sleep(1800)
            try:
                await channel.delete(reason="Время дуэльной комнаты вышло")
            except:
                pass
        self.bot.loop.create_task(_delete_channel())

async def setup(bot):
    await bot.add_cog(Duels(bot))
