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

# ─── ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ ───────────────────────────────────────────────────

class NicknameSelectView(View):
    def __init__(self, user_data):
        super().__init__(timeout=60)
        self.user_data = user_data

    @discord.ui.select(cls=UserSelect, placeholder="Выбери участника...", custom_id="nick_user_select")
    async def select_user(self, interaction: discord.Interaction, select: UserSelect):
        target = select.values[0]
        await interaction.response.send_modal(NicknameModal(target, self.user_data))

class NicknameModal(Modal):
    def __init__(self, target, user_data):
        super().__init__(title=f"🏷️ Ник для {target.display_name}")
        self.target = target
        self.user_data = user_data
        self.nick_input = TextInput(label="Новый ник", placeholder="Введи что-то смешное...", min_length=2, max_length=32)
        self.add_item(self.nick_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        price = SHOP_ITEMS["nickname"]["price"]
        current_data = await db.get_user(str(interaction.user.id))
        if current_data.get('vibecoins', 0) < price:
            await interaction.followup.send("❌ Коины закончились!", ephemeral=True)
            return

        old_nick = self.target.display_name
        try:
            await self.target.edit(nick=self.nick_input.value)
            new_bal = current_data['vibecoins'] - price
            await db.update_user(str(interaction.user.id), vibecoins=new_bal, shop_spent=current_data.get('shop_spent', 0) + price)
            await interaction.followup.send(f"✅ Ник {self.target.mention} изменен на **{self.nick_input.value}**!", ephemeral=True)
            async def _reset():
                await asyncio.sleep(3600)
                try: await self.target.edit(nick=old_nick)
                except: pass
            asyncio.create_task(_reset())
        except discord.Forbidden:
            await interaction.followup.send("❌ У бота нет прав менять ник этому пользователю.", ephemeral=True)

class FakeStatusModal(Modal):
    def __init__(self, user_data):
        super().__init__(title="🎭 Фейковый статус")
        self.user_data = user_data
        self.status_input = TextInput(label="Твой статус (приписка)", placeholder="Например: [АФК] или [Lover]", max_length=15)
        self.add_item(self.status_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        price = SHOP_ITEMS["fake_status"]["price"]
        current_data = await db.get_user(str(interaction.user.id))
        if current_data.get('vibecoins', 0) < price:
            await interaction.followup.send("❌ Недостаточно средств!", ephemeral=True)
            return

        new_nick = f"{interaction.user.display_name} | {self.status_input.value}"
        old_nick = interaction.user.display_name
        try:
            await interaction.user.edit(nick=new_nick[:32])
            new_bal = current_data['vibecoins'] - price
            await db.update_user(str(interaction.user.id), vibecoins=new_bal, shop_spent=current_data.get('shop_spent', 0) + price)
            await interaction.followup.send(f"✅ Статус установлен! Будет действовать 1 час.", ephemeral=True)
            async def _reset():
                await asyncio.sleep(3600)
                try: await interaction.user.edit(nick=old_nick)
                except: pass
            asyncio.create_task(_reset())
        except discord.Forbidden:
            await interaction.followup.send("❌ Не могу изменить твой ник.", ephemeral=True)

class GameDuelInviteView(View):
    def __init__(self, bot, challenger, target, bet, game_type):
        super().__init__(timeout=300)
        self.bot = bot
        self.challenger = challenger
        self.target = target
        self.bet = bet
        self.game_type = game_type

    @discord.ui.button(label="Принять Вызов", style=discord.ButtonStyle.success, emoji="⚔️", custom_id="duel_btn_accept")
    async def btn_accept(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ Этот вызов не для тебя!", ephemeral=True)
            return
        
        await interaction.response.defer()
        u1_data = await db.get_user(str(self.challenger.id))
        u2_data = await db.get_user(str(self.target.id))
        
        if u1_data.get('vibecoins', 0) < self.bet or u2_data.get('vibecoins', 0) < self.bet:
            await interaction.followup.send("❌ У кого-то из участников не хватает коинов!", ephemeral=True)
            return
            
        await db.update_user(str(self.challenger.id), vibecoins=u1_data['vibecoins'] - self.bet)
        await db.update_user(str(self.target.id), vibecoins=u2_data['vibecoins'] - self.bet)
        
        for child in self.children: child.disabled = True
        await interaction.edit_original_response(view=self)
        
        if self.game_type == "bj":
            from cogs.blackjack import BlackjackDuelView
            view = BlackjackDuelView(self.bot, self.challenger, self.target, self.bet)
            await interaction.channel.send(embed=view.create_embed(), view=view)
        else:
            from cogs.quiz import fetch_question, QuizDuelView
            q = await fetch_question()
            view = QuizDuelView(self.bot, self.challenger, self.target, self.bet, q)
            await interaction.channel.send(content=f"⚔️ **БИТВА ЗНАТОКОВ!**\n💡 **ВОПРОС:** {q['q']}", view=view)

class GameDuelSelectUser(UserSelect):
    def __init__(self, bot, challenger, bet, game_type):
        super().__init__(placeholder="Выбери оппонента...", min_values=1, max_values=1, custom_id="duel_user_select")
        self.bot = bot
        self.challenger = challenger
        self.bet = bet
        self.game_type = game_type

    async def callback(self, interaction: discord.Interaction):
        target = self.values[0]
        if target.bot or target.id == self.challenger.id:
            await interaction.response.send_message("❌ Недопустимая цель!", ephemeral=True)
            return
        view = GameDuelInviteView(self.bot, self.challenger, target, self.bet, self.game_type)
        await interaction.response.send_message(content=f"⚔️ {self.challenger.mention} вызывает {target.mention}!", view=view)

class GameDuelSelectView(View):
    def __init__(self, bot, challenger, bet, game_type):
        super().__init__(timeout=60)
        self.add_item(GameDuelSelectUser(bot, challenger, bet, game_type))

# ─── SHOP VIEW ────────────────────────────────────────────────────────────────

class ShopView(View):
    def __init__(self):
        super().__init__(timeout=None)
        for i, (item_id, item_data) in enumerate(SHOP_ITEMS.items()):
            btn = Button(label=f"{item_data['name']} ({item_data['price']} 🪙)", style=discord.ButtonStyle.secondary, custom_id=f"shop_buy_{item_id}", row=i//2)
            btn.callback = self._make_callback(item_id)
            self.add_item(btn)
        
        self.add_item(Button(label="🎰 Казино", style=discord.ButtonStyle.success, custom_id="shop_btn_casino", row=2)).callback = self._casino_callback
        self.add_item(Button(label="📦 Кейс", style=discord.ButtonStyle.success, custom_id="shop_btn_case", row=2)).callback = self._case_callback
        self.add_item(Button(label="⚔️ Дуэли", style=discord.ButtonStyle.success, custom_id="shop_btn_duel", row=2)).callback = self._duel_callback
        self.add_item(Button(label="🃏 Блэкджек", style=discord.ButtonStyle.success, custom_id="shop_btn_bj", row=3)).callback = self._blackjack_room_callback
        self.add_item(Button(label="💡 Викторина", style=discord.ButtonStyle.success, custom_id="shop_btn_quiz", row=3)).callback = self._quiz_room_callback

    async def _create_room(self, interaction: discord.Interaction, name: str, title: str, view_class):
        await interaction.response.defer(ephemeral=True)
        thread = await interaction.channel.create_thread(name=f"{name}-{interaction.user.name[:10]}", type=discord.ChannelType.private_thread)
        await thread.add_user(interaction.user)
        await interaction.followup.send(f"✅ Комната создана: {thread.mention}", ephemeral=True)
        embed = discord.Embed(title=title, description=f"Привет, {interaction.user.mention}! Выбирай режим:", color=COLOR_MAIN)
        await thread.send(embed=embed, view=view_class(interaction.client))

    async def _casino_callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        thread = await interaction.channel.create_thread(name=f"🎰┃казино-{interaction.user.name[:10]}", type=discord.ChannelType.private_thread)
        await thread.add_user(interaction.user)
        from cogs.casino import CasinoView, get_casino_embed
        await thread.send(embed=get_casino_embed(interaction.user.display_name), view=CasinoView())
        await interaction.followup.send(f"✅ Стол накрыт: {thread.mention}", ephemeral=True)

    async def _blackjack_room_callback(self, interaction):
        from cogs.blackjack import BlackjackRoomView
        await self._create_room(interaction, "🃏┃блэкджек", "🃏 БЛЭКДЖЕК", BlackjackRoomView)

    async def _quiz_room_callback(self, interaction):
        from cogs.quiz import QuizRoomView
        await self._create_room(interaction, "💡┃викторина", "💡 ВИКТОРИНА", QuizRoomView)

    async def _case_callback(self, interaction): interaction.client.dispatch("create_vibe_case_room", interaction)
    async def _duel_callback(self, interaction): interaction.client.dispatch("create_duel_room", interaction)

    def _make_callback(self, item_id: str):
        async def callback(interaction: discord.Interaction):
            if item_id == "nickname":
                user_data = await db.get_user(str(interaction.user.id))
                await interaction.response.send_message("🏷️ Цель:", view=NicknameSelectView(user_data), ephemeral=True)
            elif item_id == "fake_status":
                user_data = await db.get_user(str(interaction.user.id))
                await interaction.response.send_modal(FakeStatusModal(user_data))
            else:
                await interaction.response.defer(ephemeral=True)
                user_data = await db.get_user(str(interaction.user.id))
                price = SHOP_ITEMS[item_id]["price"]
                if user_data.get("vibecoins", 0) < price:
                    await interaction.followup.send(f"❌ Не хватает коинов! Баланс: {user_data.get('vibecoins', 0)}", ephemeral=True)
                    return
                await db.update_user(str(interaction.user.id), vibecoins=user_data['vibecoins'] - price)
                await interaction.followup.send(f"✅ Куплено! Остаток: {user_data['vibecoins'] - price}", ephemeral=True)
        return callback

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(ShopView())

    @commands.command(name="setup_shop")
    @commands.has_permissions(administrator=True)
    async def setup_shop(self, ctx):
        embed = discord.Embed(title="🛒 Магазин VibeCity", description="Трать свои **VibeКоины** на бонусы и игры!\n\n*Нажми на кнопку, чтобы увидеть цену и баланс.*", color=COLOR_MAIN)
        for i, item in SHOP_ITEMS.items():
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

async def setup(bot): await bot.add_cog(Shop(bot))
