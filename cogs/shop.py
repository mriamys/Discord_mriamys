import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, UserSelect
from utils.db import db
from config import COLOR_MAIN
import asyncio
import logging
from datetime import timedelta
from cogs.casino import CasinoView

SHOP_ITEMS = {
    "nickname":    {"name": "🏷️ Погоняло",       "price": 1000, "desc": "Сменить ник любому участнику на 1 час."},
    "fake_status": {"name": "🎭 Фейковый статус", "price": 500,  "desc": "Добавляет любую приписку к твоему нику на 1 час."},
    "shut_up":     {"name": "🤐 Заткнись!",       "price": 5000, "desc": "Выдаёт мут выбранному человеку на 30 секунд. Дорого и больно!"},
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
        await channel.delete(reason="Личный бункер: 1 час истёк")
    except Exception as e:
        logging.warning(f"Не смог удалить бункер {channel}: {e}")


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


# ─── 3. Заткнись ─────────────────────────────────────────────────────────────

class ShutUpSelectView(View):
    def __init__(self, user_data: dict):
        super().__init__(timeout=60)
        self.user_data = user_data

    @discord.ui.select(cls=UserSelect, placeholder="Кого заткнуть?", min_values=1, max_values=1)
    async def user_select(self, interaction: discord.Interaction, select: UserSelect):
        target = interaction.guild.get_member(select.values[0].id)
        if not target or target.bot:
            await interaction.response.send_message("❌ Нельзя заткнуть этого пользователя.", ephemeral=True)
            return
        if target.id == interaction.user.id:
            await interaction.response.send_message("❌ Нельзя заткнуть самого себя!", ephemeral=True)
            return

        new_balance = await deduct(interaction, "shut_up", self.user_data)
        try:
            await target.timeout(timedelta(seconds=30), reason=f"Куплен мут игроком {interaction.user.display_name}")
        except discord.Forbidden:
            await refund(interaction.user.id, "shut_up")
            await interaction.response.send_message(
                "❌ Нет прав заткнуть этого участника (он выше бота в иерархии).", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"🤐 **{target.display_name}** заткнут на **30 секунд**! Наслаждайся тишиной.\n"
            f"Остаток: {new_balance} 🪙", ephemeral=True
        )


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
            label="🎰 VIP Казино",
            style=discord.ButtonStyle.success,
            custom_id="shop_casino",
            emoji="🎟️"
        )
        casino_btn.callback = self._casino_callback
        self.add_item(casino_btn)

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

        await interaction.followup.send(f"✅ Твой VIP-стол накрыт: {channel.mention}", ephemeral=True)
        
        embed = discord.Embed(
            title=f"🎰 Личный VIP-стол: {interaction.user.display_name}",
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

            elif item_id == "shut_up":
                await interaction.response.send_message(
                    "🤐 Кого хочешь заткнуть?", view=ShutUpSelectView(user_data), ephemeral=True
                )

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

        await ctx.send(embed=embed, view=ShopView())
        await ctx.message.delete()


async def setup(bot):
    await bot.add_cog(Shop(bot))
