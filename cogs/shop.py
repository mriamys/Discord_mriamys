import discord
from discord.ext import commands
from discord.ui import View, Button, UserSelect, Modal, TextInput
from utils.db import db
from config import COLOR_MAIN, COLOR_SUCCESS, COLOR_ERROR
import asyncio
import random
from datetime import datetime, timedelta

SHOP_ITEMS = {
    "nickname":    {"name": "🏷️ Погоняло",       "price": 1000, "desc": "Сменить ник любому участнику на 1 час."},
    "fake_status": {"name": "🎭 Фейковый статус", "price": 500,  "desc": "Добавляет любую приписку к твоему нику на 1 час."},
    "xp_boost":    {"name": "⚡ Буст опыта x2", "price": 2500, "desc": "Удваивает весь получаемый опыт в чате и голосе на 2 часа."},
    "voice_meme":  {"name": "🔊 Рандомный высер", "price": 2000, "desc": "Бот будет заходить к тебе в войс и кидать мемные звуки целый час."}
}

# ─── ИНВАЙТЫ НА ДУЭЛИ ─────────────────────────────────────────────────────────

class GameDuelInviteView(View):
    def __init__(self, bot, challenger_id, target_id, bet, game_type):
        super().__init__(timeout=300)
        self.bot, self.challenger_id, self.target_id, self.bet, self.game_type = bot, challenger_id, target_id, bet, game_type

    @discord.ui.button(label="Принять Вызов", style=discord.ButtonStyle.success, emoji="⚔️", custom_id="duel_accept_v3")
    async def btn_accept(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ Этот вызов не для тебя!", ephemeral=True); return
        await interaction.response.defer()
        challenger = interaction.guild.get_member(self.challenger_id)
        if not challenger:
            await interaction.followup.send("❌ Инициатор покинул сервер."); return
        u1_data = await db.get_user(str(self.challenger_id))
        u2_data = await db.get_user(str(self.target_id))
        if u1_data.get('vibecoins', 0) < self.bet or u2_data.get('vibecoins', 0) < self.bet:
            await interaction.followup.send("❌ У кого-то не хватает коинов!"); return
        await db.update_user(str(self.challenger_id), vibecoins=u1_data['vibecoins'] - self.bet)
        await db.update_user(str(self.target_id), vibecoins=u2_data['vibecoins'] - self.bet)
        for child in self.children: child.disabled = True
        await interaction.edit_original_response(view=self)
        if self.game_type == "bj":
            from cogs.blackjack import BlackjackDuelView
            view = BlackjackDuelView(self.bot, challenger, interaction.user, self.bet)
            await interaction.channel.send(embed=view.create_embed(), view=view)
        else:
            from cogs.quiz import fetch_question, QuizDuelView
            q = await fetch_question()
            view = QuizDuelView(self.bot, challenger, interaction.user, self.bet, q)
            await interaction.channel.send(content=f"⚔️ **БИТВА ЗНАТОКОВ!**\n💡 **ВОПРОС:** {q['q']}", view=view)

class GameDuelSelectUser(UserSelect):
    def __init__(self, bot, challenger_id, bet, game_type):
        super().__init__(placeholder="Выбери оппонента...", min_values=1, max_values=1, custom_id="duel_select_v3")
        self.bot, self.challenger_id, self.bet, self.game_type = bot, challenger_id, bet, game_type
    async def callback(self, interaction: discord.Interaction):
        target = self.values[0]
        if target.bot or target.id == self.challenger_id:
            await interaction.response.send_message("❌ Недопустимая цель!", ephemeral=True); return
        try: await interaction.channel.add_user(target)
        except: pass
        view = GameDuelInviteView(self.bot, self.challenger_id, target.id, self.bet, self.game_type)
        await interaction.response.send_message(content=f"⚔️ <@{self.challenger_id}> вызывает {target.mention} на дуэль!", view=view)

class GameDuelSelectView(View):
    def __init__(self, bot, challenger_id, bet, game_type):
        super().__init__(timeout=60)
        self.add_item(GameDuelSelectUser(bot, challenger_id, bet, game_type))

# ─── ВСПОМОГАТЕЛЬНЫЕ МОДАЛКИ ──────────────────────────────────────────────────

class NicknameModal(Modal):
    def __init__(self, target):
        super().__init__(title=f"🏷️ Ник для {target.display_name}")
        self.target = target
        self.nick_input = TextInput(label="Новый ник", placeholder="Введи что-то...", min_length=2, max_length=32)
        self.add_item(self.nick_input)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < 1000:
            await interaction.followup.send("❌ Мало коинов!", ephemeral=True); return
        old_nick = self.target.display_name
        try:
            await self.target.edit(nick=self.nick_input.value)
            await db.update_user(str(interaction.user.id), vibecoins=user_data['vibecoins'] - 1000)
            await interaction.followup.send(f"✅ Готово!", ephemeral=True)
            async def _reset():
                await asyncio.sleep(3600)
                try: await self.target.edit(nick=old_nick)
                except: pass
            asyncio.create_task(_reset())
        except: await interaction.followup.send("❌ Ошибка.", ephemeral=True)

class NicknameSelectView(View):
    def __init__(self): super().__init__(timeout=60)
    @discord.ui.select(cls=UserSelect, placeholder="Выбери цель...")
    async def select_user(self, interaction: discord.Interaction, select: UserSelect):
        await interaction.response.send_modal(NicknameModal(select.values[0]))

class FakeStatusModal(Modal):
    def __init__(self):
        super().__init__(title="🎭 Фейковый статус")
        self.status_input = TextInput(label="Статус", placeholder="[BOSS]", max_length=15)
        self.add_item(self.status_input)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < 500:
            await interaction.followup.send("❌ Мало коинов!", ephemeral=True); return
        old_nick = interaction.user.display_name
        try:
            await interaction.user.edit(nick=f"{old_nick} | {self.status_input.value}"[:32])
            await db.update_user(str(interaction.user.id), vibecoins=user_data['vibecoins'] - 500)
            await interaction.followup.send(f"✅ Готово!", ephemeral=True)
            async def _reset():
                await asyncio.sleep(3600)
                try: await interaction.user.edit(nick=old_nick)
                except: pass
            asyncio.create_task(_reset())
        except: await interaction.followup.send("❌ Ошибка.", ephemeral=True)

# ─── SHOP VIEW ────────────────────────────────────────────────────────────────

class ShopView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _check_existing_thread(self, interaction: discord.Interaction, prefix: str):
        search_name = f"{interaction.user.name[:10]}".lower()
        for thread in interaction.channel.threads:
            if not thread.archived and prefix in thread.name.lower() and search_name in thread.name.lower():
                return thread
        return None

    @discord.ui.button(label="🏷️ Погоняло (1k)", style=discord.ButtonStyle.secondary, custom_id="shop_nick", row=0)
    async def buy_nickname(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🏷️ Выбери цель:", view=NicknameSelectView(), ephemeral=True)

    @discord.ui.button(label="🎭 Фейк Статус (500)", style=discord.ButtonStyle.secondary, custom_id="shop_status", row=0)
    async def buy_status(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(FakeStatusModal())

    @discord.ui.button(label="🎰 Казино", style=discord.ButtonStyle.success, custom_id="shop_casino_v2", row=1)
    async def go_casino(self, interaction: discord.Interaction, button: Button):
        existing = await self._check_existing_thread(interaction, "казино-")
        if existing:
            await interaction.response.send_message(f"❌ У тебя уже есть открытый стол: {existing.mention}", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        thread = await interaction.channel.create_thread(name=f"🎰┃казино-{interaction.user.name[:10]}", type=discord.ChannelType.private_thread)
        await thread.add_user(interaction.user)
        if interaction.guild.owner: await thread.add_user(interaction.guild.owner)
        from cogs.casino import CasinoView, get_casino_embed
        await thread.send(embed=get_casino_embed(interaction.user.display_name), view=CasinoView())
        await interaction.followup.send(f"✅ Ветка создана: {thread.mention}", ephemeral=True)

    @discord.ui.button(label="📦 Кейсы", style=discord.ButtonStyle.success, custom_id="shop_cases_v2", row=1)
    async def go_cases(self, interaction: discord.Interaction, button: Button):
        existing = await self._check_existing_thread(interaction, "кейс-")
        if existing:
            await interaction.response.send_message(f"❌ У тебя уже есть открытая комната с кейсами: {existing.mention}", ephemeral=True); return
        interaction.client.dispatch("create_vibe_case_room", interaction)

    @discord.ui.button(label="⚔️ Дуэли", style=discord.ButtonStyle.success, custom_id="shop_duels_v2", row=1)
    async def go_duels(self, interaction: discord.Interaction, button: Button):
        existing = await self._check_existing_thread(interaction, "дуэль-")
        if existing:
            await interaction.response.send_message(f"❌ У тебя уже есть активная комната дуэлей: {existing.mention}", ephemeral=True); return
        interaction.client.dispatch("create_duel_room", interaction)

    @discord.ui.button(label="🃏 Блэкджек", style=discord.ButtonStyle.success, custom_id="shop_bj_v2", row=2)
    async def go_bj(self, interaction: discord.Interaction, button: Button):
        existing = await self._check_existing_thread(interaction, "блэкджек-")
        if existing:
            await interaction.response.send_message(f"❌ Твой стол для Блэкджека уже ждет тебя: {existing.mention}", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        thread = await interaction.channel.create_thread(name=f"🃏┃блэкджек-{interaction.user.name[:10]}", type=discord.ChannelType.private_thread)
        await thread.add_user(interaction.user)
        if interaction.guild.owner: await thread.add_user(interaction.guild.owner)
        from cogs.blackjack import BlackjackRoomView
        desc = (
            "**Суть игры:** Нужно собрать сумму карт как можно ближе к **21**, но не больше.\n\n"
            "**Как считать очки:**\n"
            "▫️ Карты с цифрами (**2-10**) = по номиналу.\n"
            "▫️ Картинки (**Валет, Дама, Король**) = всегда **10 очков**.\n"
            "▫️ **Туз** = **11** или **1** (бот выберет лучшее для тебя).\n\n"
            "**Твой ход:**\n"
            "Нажми **Hit**, чтобы взять карту, или **Stand**, чтобы остановиться.\n"
            "⚠️ Если наберешь больше 21 — ты сразу проиграл!"
        )
        await thread.send(embed=discord.Embed(title="🃏 ИГРОВОЙ СТОЛ: БЛЭКДЖЕК", description=desc, color=COLOR_MAIN), view=BlackjackRoomView(interaction.client))
        await interaction.followup.send(f"✅ Стол накрыт: {thread.mention}", ephemeral=True)

    @discord.ui.button(label="💡 Викторина", style=discord.ButtonStyle.success, custom_id="shop_quiz_v2", row=2)
    async def go_quiz(self, interaction: discord.Interaction, button: Button):
        existing = await self._check_existing_thread(interaction, "викторина-")
        if existing:
            await interaction.response.send_message(f"❌ Ты еще не закончил в старой комнате викторины: {existing.mention}", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        thread = await interaction.channel.create_thread(name=f"💡┃викторина-{interaction.user.name[:10]}", type=discord.ChannelType.private_thread)
        await thread.add_user(interaction.user)
        if interaction.guild.owner: await thread.add_user(interaction.guild.owner)
        from cogs.quiz import QuizRoomView
        desc = (
            "**Правила Викторины:**\n"
            "🔹 **Соло:** Один случайный вопрос. Награда от **300 до 600 🪙**.\n"
            "🔹 **Сыграть с другом:** Вы видите один вопрос. **Кто первый** правильно нажмет — забирает банк!\n\n"
            "Выбирай режим игры ниже:"
        )
        await thread.send(embed=discord.Embed(title="💡 ВИКТОРИНА", description=desc, color=COLOR_MAIN), view=QuizRoomView(interaction.client))
        await interaction.followup.send(f"✅ Комната готова: {thread.mention}", ephemeral=True)

# ─── SHOP COG ─────────────────────────────────────────────────────────────────

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(ShopView())

    @commands.command(name="setup_shop")
    @commands.has_permissions(administrator=True)
    async def setup_shop(self, ctx):
        embed = discord.Embed(title="🛒 Магазин VibeCity", description="Трать свои **VibeКоины** на бонусы и игры!", color=COLOR_MAIN)
        for name, item in SHOP_ITEMS.items():
            embed.add_field(name=f"{item['name']} — {item['price']} 🪙", value=f"*{item['desc']}*", inline=False)
        embed.add_field(name="──────────────", value="**🎮 ИГРОВЫЕ КОМНАТЫ**", inline=False)
        embed.set_image(url="https://media.giphy.com/media/xUPGGw7jzcqeMw5dI8/giphy.gif")
        
        old_msg_id = await db.get_setting("shop_message_id")
        old_ch_id = await db.get_setting("shop_channel_id")
        if old_msg_id and old_ch_id:
            try:
                ch = self.bot.get_channel(int(old_ch_id))
                msg = await ch.fetch_message(int(old_msg_id))
                await msg.delete()
            except: pass

        new_msg = await ctx.send(embed=embed, view=ShopView())
        await db.set_setting("shop_message_id", str(new_msg.id))
        await db.set_setting("shop_channel_id", str(ctx.channel.id))
        try: await ctx.message.delete()
        except: pass

    @commands.command(name="clear_threads", aliases=["чистка_веток", "удалить_румы"])
    @commands.has_permissions(administrator=True)
    async def clear_threads(self, ctx):
        """Удаляет все игровые ветки в текущем канале (включая невидимые)."""
        await ctx.send("🔍 Ищу активные игровые комнаты для удаления...")
        deleted_count = 0
        prefixes = ["🎰┃казино-", "📦┃кейс-", "⚔️┃дуэль-", "🃏┃блэкджек-", "💡┃викторина-"]
        for thread in ctx.channel.threads:
            if any(thread.name.startswith(p) for p in prefixes):
                try: await thread.delete(); deleted_count += 1
                except: pass
        async for thread in ctx.channel.archived_threads(private=True):
            if any(thread.name.startswith(p) for p in prefixes):
                try: await thread.delete(); deleted_count += 1
                except: pass
        await ctx.send(f"✅ Чистка завершена! Удалено комнат: **{deleted_count}**")

async def setup(bot): await bot.add_cog(Shop(bot))
