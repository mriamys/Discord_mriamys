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

class NicknameModal(Modal):
    def __init__(self, target):
        super().__init__(title=f"🏷️ Ник для {target.display_name}")
        self.target = target
        self.nick_input = TextInput(label="Новый ник", placeholder="Введи что-то...", min_length=2, max_length=32)
        self.add_item(self.nick_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        price = SHOP_ITEMS["nickname"]["price"]
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < price:
            await interaction.followup.send("❌ Недостаточно VibeКоинов!", ephemeral=True)
            return

        old_nick = self.target.display_name
        try:
            await self.target.edit(nick=self.nick_input.value)
            await db.update_user(str(interaction.user.id), vibecoins=user_data['vibecoins'] - price)
            await interaction.followup.send(f"✅ Ник {self.target.mention} изменен! Списано {price} 🪙", ephemeral=True)
            async def _reset():
                await asyncio.sleep(3600)
                try: await self.target.edit(nick=old_nick)
                except: pass
            asyncio.create_task(_reset())
        except:
            await interaction.followup.send("❌ Ошибка прав доступа.", ephemeral=True)

class NicknameSelectView(View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(cls=UserSelect, placeholder="Выбери участника...")
    async def select_user(self, interaction: discord.Interaction, select: UserSelect):
        target = select.values[0]
        await interaction.response.send_modal(NicknameModal(target))

class FakeStatusModal(Modal):
    def __init__(self):
        super().__init__(title="🎭 Фейковый статус")
        self.status_input = TextInput(label="Твой статус (приписка)", placeholder="Например: [BOSS]", max_length=15)
        self.add_item(self.status_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        price = SHOP_ITEMS["fake_status"]["price"]
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < price:
            await interaction.followup.send("❌ Недостаточно VibeКоинов!", ephemeral=True)
            return

        new_nick = f"{interaction.user.display_name} | {self.status_input.value}"
        old_nick = interaction.user.display_name
        try:
            await interaction.user.edit(nick=new_nick[:32])
            await db.update_user(str(interaction.user.id), vibecoins=user_data['vibecoins'] - price)
            await interaction.followup.send(f"✅ Статус установлен на 1 час!", ephemeral=True)
            async def _reset():
                await asyncio.sleep(3600)
                try: await interaction.user.edit(nick=old_nick)
                except: pass
            asyncio.create_task(_reset())
        except:
            await interaction.followup.send("❌ Не удалось изменить ник.", ephemeral=True)

# ─── ГЛАВНЫЙ ВЬЮ МАГАЗИНА ─────────────────────────────────────────────────────

class ShopView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🏷️ Погоняло (1k)", style=discord.ButtonStyle.secondary, custom_id="shop_buy_nick", row=0)
    async def buy_nickname(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🏷️ Выбери, кому хочешь сменить ник:", view=NicknameSelectView(), ephemeral=True)

    @discord.ui.button(label="🎭 Фейк Статус (500)", style=discord.ButtonStyle.secondary, custom_id="shop_buy_status", row=0)
    async def buy_status(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(FakeStatusModal())

    @discord.ui.button(label="⚡ Буст XP x2 (2.5k)", style=discord.ButtonStyle.secondary, custom_id="shop_buy_xp", row=1)
    async def buy_xp(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        price = SHOP_ITEMS["xp_boost"]["price"]
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < price:
            await interaction.followup.send(f"❌ Нужно {price} 🪙. У тебя {user_data.get('vibecoins', 0)}", ephemeral=True)
            return
        await db.update_user(str(interaction.user.id), vibecoins=user_data['vibecoins'] - price, xp_boost_until=datetime.utcnow() + timedelta(hours=2))
        await interaction.followup.send(f"✅ Буст опыта x2 активирован на 2 часа! Баланс: {user_data['vibecoins'] - price} 🪙", ephemeral=True)

    @discord.ui.button(label="🔊 Рандом Мемы (2k)", style=discord.ButtonStyle.secondary, custom_id="shop_buy_meme", row=1)
    async def buy_meme(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        price = SHOP_ITEMS["voice_meme"]["price"]
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < price:
            await interaction.followup.send(f"❌ Нужно {price} 🪙", ephemeral=True)
            return
        await db.update_user(str(interaction.user.id), vibecoins=user_data['vibecoins'] - price, voice_memes_until=datetime.utcnow() + timedelta(hours=1), voice_memes_count=0)
        await interaction.followup.send("🔊 Заказ принят! Жди мемы в войсе.", ephemeral=True)

    @discord.ui.button(label="🎰 Казино", style=discord.ButtonStyle.success, custom_id="shop_go_casino", row=2)
    async def go_casino(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        thread = await interaction.channel.create_thread(name=f"🎰┃казино-{interaction.user.name[:10]}", type=discord.ChannelType.private_thread)
        await thread.add_user(interaction.user)
        from cogs.casino import CasinoView, get_casino_embed
        await thread.send(embed=get_casino_embed(interaction.user.display_name), view=CasinoView())
        await interaction.followup.send(f"✅ Ветка создана: {thread.mention}", ephemeral=True)

    @discord.ui.button(label="📦 Кейсы", style=discord.ButtonStyle.success, custom_id="shop_go_cases", row=2)
    async def go_cases(self, interaction: discord.Interaction, button: Button):
        interaction.client.dispatch("create_vibe_case_room", interaction)

    @discord.ui.button(label="⚔️ Дуэли", style=discord.ButtonStyle.success, custom_id="shop_go_duels", row=2)
    async def go_duels(self, interaction: discord.Interaction, button: Button):
        interaction.client.dispatch("create_duel_room", interaction)

    @discord.ui.button(label="🃏 Блэкджек", style=discord.ButtonStyle.success, custom_id="shop_go_bj", row=3)
    async def go_bj(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        thread = await interaction.channel.create_thread(name=f"🃏┃блэкджек-{interaction.user.name[:10]}", type=discord.ChannelType.private_thread)
        await thread.add_user(interaction.user)
        from cogs.blackjack import BlackjackRoomView
        desc = (
            "**Правила игры:**\n"
            "Набери больше очков, чем у дилера, но не более **21**.\n"
            "🔹 **Туз:** 1 или 11 очков. 🔹 **Картинки:** 10 очков.\n"
            "🤖 Дилер всегда берет карты до 17 очков.\n\n"
            "Выбирай режим игры ниже:"
        )
        embed = discord.Embed(title="🃏 БЛЭКДЖЕК", description=desc, color=COLOR_MAIN)
        await thread.send(embed=embed, view=BlackjackRoomView(interaction.client))
        await interaction.followup.send(f"✅ Твой игровой стол: {thread.mention}", ephemeral=True)

    @discord.ui.button(label="💡 Викторина", style=discord.ButtonStyle.success, custom_id="shop_go_quiz", row=3)
    async def go_quiz(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        thread = await interaction.channel.create_thread(name=f"💡┃викторина-{interaction.user.name[:10]}", type=discord.ChannelType.private_thread)
        await thread.add_user(interaction.user)
        from cogs.quiz import QuizRoomView
        desc = (
            "**Правила Викторины:**\n"
            "🔹 **Соло:** Один случайный вопрос. Награда от **300 до 600 🪙**.\n"
            "🔹 **Сыграть с другом:** Вы видите один вопрос. **Кто первый** правильно нажмет — забирает весь банк!\n\n"
            "Выбирай режим игры ниже:"
        )
        embed = discord.Embed(title="💡 ВИКТОРИНА", description=desc, color=COLOR_MAIN)
        await thread.send(embed=embed, view=QuizRoomView(interaction.client))
        await interaction.followup.send(f"✅ Игровая комната: {thread.mention}", ephemeral=True)

# ─── Shop Cog ─────────────────────────────────────────────────────────────────

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(ShopView())

    @commands.command(name="setup_shop")
    @commands.has_permissions(administrator=True)
    async def setup_shop(self, ctx):
        embed = discord.Embed(
            title="🛒 Магазин VibeCity", 
            description="Трать свои **VibeКоины** на крутые бонусы и развлечения!\n\n*Нажми на кнопку товара, чтобы увидеть цену и свой баланс.*", 
            color=COLOR_MAIN
        )
        for item in SHOP_ITEMS.values():
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

async def setup(bot):
    await bot.add_cog(Shop(bot))
