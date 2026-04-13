import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, UserSelect
from utils.db import db
from config import COLOR_MAIN
import asyncio
import logging
from datetime import datetime, timedelta
from cogs.casino import CasinoView

SHOP_ITEMS = {
    "nickname":    {"name": "🏷️ Погоняло",       "price": 1000, "desc": "Сменить ник любому участнику на 1 час."},
    "fake_status": {"name": "🎭 Фейковый статус", "price": 500,  "desc": "Добавляет любую приписку к твоему нику на 1 час."},
    "xp_boost":    {"name": "⚡ Буст опыта x2", "price": 2500, "desc": "Удваивает весь получаемый опыт в чате и голосе на 2 часа."},
    "voice_meme":  {"name": "🔊 Рандомный высер", "price": 2000, "desc": "Бот будет заходить к тебе в войс и кидать мемные звуки целый час (до 10 раз)."}
}

# ─── Вспомогательные функции ──────────────────────────────────────────────────

async def check_balance(interaction, item_id):
    """Проверяет баланс. Возвращает user_data или None."""
    user_data = await db.get_user(str(interaction.user.id))
    balance = user_data.get("vibecoins", 0)
    price = SHOP_ITEMS[item_id]["price"]
    if balance < price:
        await interaction.response.send_message(
            f"❌ Не хватает **VibeКоинов**! У тебя {balance}/{price} 🪙", ephemeral=True
        )
        return None
    return user_data

async def deduct(interaction, item_id, user_data):
    """Списывает монеты и диспатчит ивент."""
    price = SHOP_ITEMS[item_id]["price"]
    new_balance = user_data.get("vibecoins", 0) - price
    shop_spent = user_data.get("shop_spent", 0) + price
    nick_changes = user_data.get("nick_changes", 0)
    if item_id in ("nickname", "fake_status"):
        nick_changes += 1
    await db.update_user(str(interaction.user.id), vibecoins=new_balance, shop_spent=shop_spent, nick_changes=nick_changes)
    interaction.client.dispatch("shop_purchased", interaction.user, item_id, shop_spent, nick_changes)
    return new_balance

async def refund(user_id, item_id):
    """Возвращает монеты если что-то пошло не так."""
    user_data = await db.get_user(str(user_id))
    await db.update_user(str(user_id), vibecoins=user_data.get("vibecoins", 0) + SHOP_ITEMS[item_id]["price"])

async def _revert_nick(member: discord.Member, original_nick: str | None, delay: int = 3600):
    await asyncio.sleep(delay)
    try:
        await member.edit(nick=original_nick)
    except Exception as e:
        logging.warning(f"Не смог вернуть ник {member}: {e}")

async def _delete_channel(channel: discord.TextChannel, delay: int = 3600):
    await asyncio.sleep(delay)
    try:
        await channel.delete(reason="Время стола/Бункера истёкло")
    except Exception as e:
        logging.Traceback(e)


# ─── 1. Погоняло ─────────────────────────────────────────────────────────────

class NicknameModal(Modal, title="🏷️ Какое погоняло дать?"):
    new_nick = TextInput(label="Новый никнейм", placeholder="Введи ник (макс. 32 символа)", max_length=32)

    def __init__(self, target: discord.Member, user_data: dict):
        super().__init__()
        self.target = target
        self.user_data = user_data

    async def on_submit(self, interaction: discord.Interaction):
        new_balance = await deduct(interaction, "nickname", self.user_data)
        old_nick = self.target.nick  # None если ник не задан (используется display_name)
        display_old = self.target.display_name
        try:
            await self.target.edit(nick=self.new_nick.value)
        except discord.Forbidden:
            await refund(interaction.user.id, "nickname")
            await interaction.response.send_message(
                "❌ Нет прав сменить ник этому участнику (он выше бота в иерархии).", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Игроку **{display_old}** дали погоняло **{self.new_nick.value}** на 1 час!\n"
            f"Остаток: {new_balance} 🪙", ephemeral=True
        )
        asyncio.create_task(_revert_nick(self.target, old_nick, delay=3600))


class NicknameSelectView(View):
    def __init__(self, user_data: dict):
        super().__init__(timeout=60)
        self.user_data = user_data

    @discord.ui.select(cls=UserSelect, placeholder="Выбери жертву...", min_values=1, max_values=1)
    async def user_select(self, interaction: discord.Interaction, select: UserSelect):
        target = interaction.guild.get_member(select.values[0].id)
        if not target or target.bot:
            await interaction.response.send_message("❌ Нельзя выбрать этого пользователя.", ephemeral=True)
            return
        if target.id == interaction.user.id:
            await interaction.response.send_message("❌ Нельзя самому себе давать погоняло!", ephemeral=True)
            return
        await interaction.response.send_modal(NicknameModal(target, self.user_data))


# ─── 2. Фейковый статус ───────────────────────────────────────────────────────

class FakeStatusModal(Modal, title="🎭 Что добавить к нику?"):
    suffix = TextInput(label="Приписка", placeholder="Например:  | ЧМО |  или  🤡", max_length=20)

    def __init__(self, user_data: dict):
        super().__init__()
        self.user_data = user_data

    async def on_submit(self, interaction: discord.Interaction):
        new_balance = await deduct(interaction, "fake_status", self.user_data)
        old_nick = interaction.user.nick  # None = оригинальный ник
        display_old = interaction.user.display_name
        new_nick_str = f"{display_old} {self.suffix.value}"[:32]
        try:
            await interaction.user.edit(nick=new_nick_str)
        except discord.Forbidden:
            await refund(interaction.user.id, "fake_status")
            await interaction.response.send_message(
                "❌ Не могу сменить твой ник (Owner или выше бота).", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ К твоему нику добавлен статус **{self.suffix.value}** на 1 час!\n"
            f"Остаток: {new_balance} 🪙", ephemeral=True
        )
        asyncio.create_task(_revert_nick(interaction.user, old_nick, delay=3600))


# ─── Удален пункт Заткнись ───────────────────────────────────────────────────

# ─── 4. Главный ShopView ──────────────────────────────────────────────────────

class ShopView(View):
    def __init__(self):
        super().__init__(timeout=None)
        for item_id, item_data in SHOP_ITEMS.items():
            button = Button(
                label=f"{item_data['name']} ({item_data['price']} 🪙)",
                style=discord.ButtonStyle.secondary,
                custom_id=f"shop_{item_id}"
            )
            button.callback = self._make_callback(item_id)
            self.add_item(button)
        
        # Кнопка личного казино
        casino_btn = Button(
            label="🎰 Казино",
            style=discord.ButtonStyle.success,
            custom_id="shop_casino",
            row=1
        )
        casino_btn.callback = self._casino_callback
        self.add_item(casino_btn)
        
        # Кнопка открытия руммы для кейсов
        case_btn = Button(
            label="📦 Кейс",
            style=discord.ButtonStyle.success,
            custom_id="shop_case",
            row=1
        )
        case_btn.callback = self._case_callback
        self.add_item(case_btn)
        
        # Кнопка руммы дуэлей
        duel_btn = Button(
            label="⚔️ Дуэли",
            style=discord.ButtonStyle.success,
            custom_id="shop_duel",
            row=1
        )
        duel_btn.callback = self._duel_callback
        self.add_item(duel_btn)

    async def _case_callback(self, interaction: discord.Interaction):
        interaction.client.dispatch("create_vibe_case_room", interaction)

    async def _duel_callback(self, interaction: discord.Interaction):
        interaction.client.dispatch("create_duel_room", interaction)

    async def _casino_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # Проверяем не создан ли уже канал
        guild = interaction.guild
        channel_name = f"казино-{interaction.user.name[:15]}"
        existing = discord.utils.get(guild.channels, name=channel_name.lower())
        if existing:
            await interaction.followup.send(f"У тебя уже есть открытый стол: {existing.mention}", ephemeral=True)
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
                topic=f"Личный казино-стол для {interaction.user.display_name} 🎰"
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ У бота нет прав для создания приватного канала.", ephemeral=True)
            return

        await interaction.followup.send(f"✅ Твой личный стол накрыт: {channel.mention}", ephemeral=True)
        
        embed = discord.Embed(
            title=f"🎰 Личный стол: {interaction.user.display_name}",
            description=(
                "Добро пожаловать в закрытый клуб! Умножай свои **VibeКоины** в тишине и покое.\n\n"
                "**🎰 Слоты** — классика. 3 в ряд до **x50**!\n"
                "**🪙 Монетка** — 50/50. Выигрыш **x1.95**\n"
                "**🎲 Кости** — угадай число 1–6 и получи **x5.5**!\n\n"
                "Жми кнопку ниже, чтобы сделать ставку. Когда закончишь, нажми **Выйти**, чтобы закрыть этот стол."
            ),
            color=0xF1C40F
        )
        embed.set_image(url="https://media.giphy.com/media/3ohzdFmHSiRBbhzaE8/giphy.gif")
        await channel.send(content=interaction.user.mention, embed=embed, view=CasinoView())
        asyncio.create_task(_delete_channel(channel, 3600))

    def _make_callback(self, item_id: str):
        async def callback(interaction: discord.Interaction):
            user_data = await check_balance(interaction, item_id)
            if user_data is None:
                return  # check_balance уже ответил с ошибкой

            if item_id == "nickname":
                await interaction.response.send_message(
                    "🏷️ Выбери кому давать погоняло:", view=NicknameSelectView(user_data), ephemeral=True
                )

            elif item_id == "fake_status":
                await interaction.response.send_modal(FakeStatusModal(user_data))

            elif item_id == "xp_boost":
                new_balance = await deduct(interaction, "xp_boost", user_data)
                until = datetime.utcnow() + timedelta(hours=2)
                await db.update_user(str(interaction.user.id), xp_boost_until=until)
                interaction.client.dispatch("boost_purchased", interaction.user)
                await interaction.response.send_message(f"⚡ Буст опыта x2 успешно куплен и активен на следующие 2 часа!\nОстаток: {new_balance} 🪙", ephemeral=True)

            elif item_id == "voice_meme":
                if not interaction.user.voice:
                    await interaction.response.send_message("❌ Ты должен быть в голосовом канале, чтобы купить высеры!", ephemeral=True)
                    return
                # Списание и регистрация будет обрабатываться диспетчером или когом audio_memes
                new_balance = await deduct(interaction, "voice_meme", user_data)
                memes = user_data.get('memes_ordered', 0) + 1
                await db.update_user(str(interaction.user.id), memes_ordered=memes)
                interaction.client.dispatch("meme_ordered", interaction.user, memes)
                interaction.client.dispatch("voice_meme_purchased", interaction.user, interaction.user.voice.channel)
                await interaction.response.send_message(f"🔊 Заказ принят! В течение часа жди аудио-троллинг в канале {interaction.user.voice.channel.mention}.\nОстаток: {new_balance} 🪙", ephemeral=True)

        return callback


# ─── Cog ─────────────────────────────────────────────────────────────────────

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="shop", description="Узнать свой баланс VibeКоинов")
    async def shop(self, ctx):
        user_data = await db.get_user(str(ctx.author.id))
        balance = user_data.get("vibecoins", 0)
        await ctx.send(
            f"🪙 Твой баланс: **{balance} VibeКоинов**\nЗагляни в канал покупок, чтобы потратить их!",
            ephemeral=True
        )

    @commands.command(name="setup_shop", aliases=["setup_store", "создать_магазин", "магазин_сетап", "магаз", "магазин"])
    @commands.has_permissions(administrator=True)
    async def setup_shop(self, ctx):
        embed = discord.Embed(
            title="🛒 Магазин Рофлов",
            description="Трать **VibeКоины** на крутые штуки!\nНажми кнопку — всё происходит автоматически.",
            color=COLOR_MAIN
        )
        embed.set_image(url="https://media.giphy.com/media/xUPGGw7jzcqeMw5dI8/giphy.gif")
        for item in SHOP_ITEMS.values():
            embed.add_field(name=f"{item['name']} — {item['price']} 🪙", value=item['desc'], inline=False)
            
        embed.add_field(name="🎰 Развлечения — Бесплатный вход", value="Жми зелёные кнопки ниже, чтобы открыть личные игровые столы с Казино, Кейсами или Дуэлями!", inline=False)

        await ctx.send(embed=embed, view=ShopView())
        await ctx.message.delete()

    @commands.Cog.listener()
    async def on_message(self, message):
        """Очищает любые сообщения в канале магазина кроме самого меню."""
        if message.author.bot:
            # Не удаляем сообщения бота (само меню магазина), 
            # но можно удалять системные сообщения Discord если нужно
            return
            
        # Проверяем, есть ли в этом канале меню магазина
        # Мы можем искать по теме канала или просто по наличию нашего сообщения с эмбедом
        # Но проще всего: если это канал с названием "магазин", "shop", "покупки"
        if any(kw in message.channel.name.lower() for kw in ["магазин", "shop", "маркет"]):
            await asyncio.sleep(10) # Даем 10 секунд почитать, если это была ошибка
            try:
                await message.delete()
            except:
                pass


async def setup(bot):
    await bot.add_cog(Shop(bot))
