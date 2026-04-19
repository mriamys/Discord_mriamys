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

    @discord.ui.button(label="Принять Вызов", style=discord.ButtonStyle.success, emoji="⚔️")
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
            await interaction.channel.send(embed=await view.create_embed(), view=view)
        else:
            from cogs.quiz import fetch_question, QuizDuelView
            q = await fetch_question()
            view = QuizDuelView(self.bot, challenger, interaction.user, self.bet, q)
            msg = await interaction.channel.send(content=f"{challenger.mention} 🆚 {interaction.user.mention}", embed=await view.create_embed(), view=view)
            view.message = msg

class GameDuelSelectUser(UserSelect):
    def __init__(self, bot, challenger_id, bet, game_type):
        super().__init__(placeholder="Выбери оппонента...", min_values=1, max_values=1)
        self.bot, self.challenger_id, self.bet, self.game_type = bot, challenger_id, bet, game_type

    async def callback(self, interaction: discord.Interaction):
        target = self.values[0]
        if target.bot or target.id == self.challenger_id:
            await interaction.response.send_message("❌ Недопустимая цель!", ephemeral=True); return
            
        await interaction.response.defer(ephemeral=True)
        try: await interaction.channel.add_user(target)
        except: pass
        
        view = GameDuelInviteView(self.bot, self.challenger_id, target.id, self.bet, self.game_type)
        await interaction.channel.send(content=f"⚔️ <@{self.challenger_id}> вызывает {target.mention} на дуэль!", view=view)
        await interaction.followup.send("✅ Вызов отправлен!", ephemeral=True)

class GameDuelSelectView(View):
    def __init__(self, bot, challenger_id, bet, game_type):
        super().__init__(timeout=60)
        self.add_item(GameDuelSelectUser(bot, challenger_id, bet, game_type))

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

    def _start_cleanup_task(self, thread):
        async def _delete_thread():
            await asyncio.sleep(300) # 5 минут вместо 30
            try: await thread.delete()
            except: pass
        asyncio.create_task(_delete_thread())

    @discord.ui.button(label="🏷️ Погоняло (1k)", style=discord.ButtonStyle.secondary, custom_id="shop_nick", row=0)
    async def buy_nickname(self, interaction, button):
        await interaction.response.send_message("🏷️ Выбери цель:", view=NicknameSelectView(), ephemeral=True)

    @discord.ui.button(label="🎭 Статус (500)", style=discord.ButtonStyle.secondary, custom_id="shop_status", row=0)
    async def buy_status(self, interaction, button):
        await interaction.response.send_modal(FakeStatusModal())

    @discord.ui.button(label="⚡ Буст XP (2.5k)", style=discord.ButtonStyle.secondary, custom_id="shop_xp_boost", row=0)
    async def buy_xp(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        u_data = await db.get_user(str(interaction.user.id))
        if u_data.get('vibecoins', 0) < 2500:
            await interaction.followup.send("❌ Мало коинов!", ephemeral=True); return
        await db.update_user(str(interaction.user.id), vibecoins=u_data['vibecoins'] - 2500, xp_boost_until=datetime.utcnow() + timedelta(hours=2))
        await interaction.followup.send("⚡ Буст x2 на 2 часа куплен!", ephemeral=True)
        interaction.client.dispatch("shop_purchased", interaction.user, "xp_boost", u_data['vibecoins'] - 2500, u_data.get('nick_changes', 0))

    @discord.ui.button(label="🔊 Мемы (2k)", style=discord.ButtonStyle.secondary, custom_id="shop_voice_meme", row=0)
    async def buy_meme(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        u_data = await db.get_user(str(interaction.user.id))
        if u_data.get('vibecoins', 0) < 2000:
            await interaction.followup.send("❌ Мало коинов!", ephemeral=True); return
        await db.update_user(str(interaction.user.id), vibecoins=u_data['vibecoins'] - 2000, voice_memes_until=datetime.utcnow() + timedelta(hours=1), voice_memes_count=0)
        await interaction.followup.send("🔊 Мемы заказаны на 1 час!", ephemeral=True)
        
        # Передаем ивент для AudioMemes
        interaction.client.dispatch("voice_meme_purchased", interaction.user, interaction.user.voice.channel if interaction.user.voice else None)
        # И для квеста/ачивок
        interaction.client.dispatch("shop_purchased", interaction.user, "voice_meme", u_data['vibecoins'] - 2000, u_data.get('nick_changes', 0))

    @discord.ui.button(label="🎰 Казино", style=discord.ButtonStyle.success, custom_id="shop_casino", row=1)
    async def go_casino(self, interaction, button):
        existing = await self._check_existing_thread(interaction, "казино-")
        if existing: await interaction.response.send_message(f"❌ Есть открытый стол: {existing.mention}", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        thread = await interaction.channel.create_thread(name=f"🎰┃казино-{interaction.user.name[:10]}", type=discord.ChannelType.private_thread)
        await thread.add_user(interaction.user)
        if interaction.guild.owner: await thread.add_user(interaction.guild.owner)
        from cogs.casino import CasinoView, get_casino_embed
        await thread.send(embed=get_casino_embed(interaction.user.display_name), view=CasinoView())
        await interaction.followup.send(f"✅ Ветка создана: {thread.mention}", ephemeral=True)
        self._start_cleanup_task(thread)

    @discord.ui.button(label="📦 Кейсы", style=discord.ButtonStyle.success, custom_id="shop_cases", row=1)
    async def go_cases(self, interaction, button):
        existing = await self._check_existing_thread(interaction, "кейс-")
        if existing: await interaction.response.send_message(f"❌ Есть открытая комната: {existing.mention}", ephemeral=True); return
        interaction.client.dispatch("create_vibe_case_room", interaction)

    @discord.ui.button(label="⚔️ Дуэли", style=discord.ButtonStyle.success, custom_id="shop_duels", row=1)
    async def go_duels(self, interaction, button):
        existing = await self._check_existing_thread(interaction, "дуэль-")
        if existing: await interaction.response.send_message(f"❌ Есть активная комната: {existing.mention}", ephemeral=True); return
        interaction.client.dispatch("create_duel_room", interaction)

    @discord.ui.button(label="🃏 Блэкджек", style=discord.ButtonStyle.success, custom_id="shop_blackjack", row=2)
    async def go_bj(self, interaction, button):
        existing = await self._check_existing_thread(interaction, "блэкджек-")
        if existing: await interaction.response.send_message(f"❌ Твой стол уже здесь: {existing.mention}", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        thread = await interaction.channel.create_thread(name=f"🃏┃блэкджек-{interaction.user.name[:10]}", type=discord.ChannelType.private_thread)
        await thread.add_user(interaction.user)
        if interaction.guild.owner: await thread.add_user(interaction.guild.owner)
        from cogs.blackjack import BlackjackRoomView
        desc = "**Суть:** Собери сумму ближе к **21**, но не больше.\n▫️ J,Q,K = 10, Туз = 11 или 1."
        await thread.send(embed=discord.Embed(title="🃏 БЛЭКДЖЕК", description=desc, color=COLOR_MAIN), view=BlackjackRoomView(interaction.client))
        await interaction.followup.send(f"✅ Готово: {thread.mention}", ephemeral=True)
        self._start_cleanup_task(thread)

    @discord.ui.button(label="💡 Викторина", style=discord.ButtonStyle.success, custom_id="shop_quiz", row=2)
    async def go_quiz(self, interaction, button):
        existing = await self._check_existing_thread(interaction, "викторина-")
        if existing: 
            await interaction.response.send_message(f"❌ Ты не закончил викторину: {existing.mention}", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        try:
            thread = await interaction.channel.create_thread(
                name=f"💡┃викторина-{interaction.user.name[:10]}", 
                type=discord.ChannelType.private_thread,
                invitable=False
            )
            await thread.add_user(interaction.user)
            if interaction.guild.owner:
                try: await thread.add_user(interaction.guild.owner)
                except: pass
            
            from cogs.quiz import QuizRoomView
            desc = "**Правила:**\n🔹 Соло: бесконечный рандом.\n🔹 Дуэль: кто первый нажал - забирает банк!"
            
            await thread.send(
                embed=discord.Embed(title="💡 ВИКТОРИНА", description=desc, color=COLOR_MAIN), 
                view=QuizRoomView(interaction.client)
            )
            await interaction.followup.send(f"✅ Готово: {thread.mention}", ephemeral=True)
            self._start_cleanup_task(thread)
        except Exception as e:
            import logging
            logging.error(f"Error creating quiz thread: {e}")
            await interaction.followup.send(f"❌ Ошибка при создании ветки: {e}", ephemeral=True)

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

    @commands.command(name="clear_threads")
    @commands.has_permissions(administrator=True)
    async def clear_threads(self, ctx):
        deleted = 0
        prefixes = ["🎰┃казино-", "📦┃кейс-", "⚔️┃дуэль-", "🃏┃блэкджек-", "💡┃викторина-"]
        for t in ctx.channel.threads:
            if any(t.name.startswith(p) for p in prefixes):
                try: await t.delete(); deleted += 1
                except: pass
        await ctx.send(f"✅ Удалено комнат: **{deleted}**")

# Заглушки
class NicknameModal(Modal):
    def __init__(self, target):
        super().__init__(title=f"🏷️ Ник для {target.display_name}")
        self.target, self.nick_input = target, TextInput(label="Новый ник", min_length=2, max_length=32)
        self.add_item(self.nick_input)
    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True)
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < 1000:
            await interaction.followup.send("❌ Мало коинов!", ephemeral=True); return
        try:
            old_nick = self.target.display_name
            await self.target.edit(nick=self.nick_input.value)
            await db.update_user(str(interaction.user.id), vibecoins=user_data['vibecoins'] - 1000)
            await interaction.followup.send(f"✅ Готово!", ephemeral=True)
            async def _res(): await asyncio.sleep(3600); await self.target.edit(nick=old_nick)
            asyncio.create_task(_res())
        except: await interaction.followup.send("❌ Ошибка.", ephemeral=True)

class NicknameSelectView(View):
    def __init__(self): super().__init__(timeout=60)
    @discord.ui.select(cls=UserSelect, placeholder="Выбери участника...")
    async def select_user(self, interaction, select): await interaction.response.send_modal(NicknameModal(select.values[0]))

class FakeStatusModal(Modal):
    def __init__(self):
        super().__init__(title="🎭 Фейковый статус")
        self.status_input = TextInput(label="Статус", placeholder="[BOSS]", max_length=15)
        self.add_item(self.status_input)
    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True)
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < 500:
            await interaction.followup.send("❌ Мало коинов!", ephemeral=True); return
        try:
            old_nick = interaction.user.display_name
            await interaction.user.edit(nick=f"{old_nick} | {self.status_input.value}"[:32])
            await db.update_user(str(interaction.user.id), vibecoins=user_data['vibecoins'] - 500)
            await interaction.followup.send(f"✅ Готово!", ephemeral=True)
            async def _res(): await asyncio.sleep(3600); await interaction.user.edit(nick=old_nick)
            asyncio.create_task(_res())
        except: await interaction.followup.send("❌ Ошибка.", ephemeral=True)

async def setup(bot): await bot.add_cog(Shop(bot))
