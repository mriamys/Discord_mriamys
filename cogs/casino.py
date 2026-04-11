import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from utils.db import db
from config import COLOR_MAIN, COLOR_SUCCESS, COLOR_ERROR
import asyncio
import random
import time

MIN_BET = 10
MAX_BET = 10_000
COOLDOWN_SEC = 20  # сек между ставками

# ─── Слоты: символы + веса + множители ──────────────────────────────────────
SYMBOLS      = ["🍒", "🍋", "🍊", "🍇", "🔔", "⭐", "💎", "7️⃣"]
WEIGHTS      = [ 35,   30,   20,   12,    8,    5,    3,    1]

def spin_slots():
    return random.choices(SYMBOLS, weights=WEIGHTS, k=3)

def calc_slots(bet: int, reels: list) -> tuple[int, str, str]:
    """(payout, result_line, footer)"""
    a, b, c = reels
    line = f"[ {a}  {b}  {c} ]"
    
    if a == b == c:
        mults = {"7️⃣": 50.0, "💎": 25.0, "⭐": 15.0, "🔔": 10.0,
                 "🍇": 5.0,  "🍊": 4.0, "🍋": 3.0, "🍒": 2.5}
        mult = mults.get(a, 2.5)
        payout = int(bet * mult)
        msg = f"🎰 **ДЖЕКПОТ!!!** x{mult:.0f}" if mult >= 15 else f"✨ **Три в ряд!** x{mult:.1f}"
        return payout, line, f"{msg} — выигрыш **{payout:,} 🪙**!"
    
    elif a == b:
        payout = bet * 2
        return payout, line, f"🎯 Два совпадения слева — x2 — выигрыш **{payout:,} 🪙**"
    
    elif a == "🍒":
        payout = bet
        return payout, line, f"🍒 Первая вишенка спасает! Возврат ставки: **{payout:,} 🪙**"
        
    return 0, line, "❌ Мимо! Попробуй ещё раз."


def flip_coin(bet: int, choice: str) -> tuple[int, str]:
    result = random.choice(["Орёл", "Решка"])
    icons  = {"Орёл": "🦅", "Решка": "💿"}
    won    = result.lower() == choice.lower()
    payout = int(bet * 1.95) if won else 0
    icon   = icons[result]
    msg    = f"{icon} Выпало **{result}**! {'🥳 Победа! **x1.95** +**' + str(payout) + ' 🪙**' if won else '💔 Проигрыш.'}"
    return payout, msg

def roll_dice(bet: int, guess: int) -> tuple[int, str]:
    result      = random.randint(1, 6)
    dice_emojis = ["⚀","⚁","⚂","⚃","⚄","⚅"]
    won         = result == guess
    payout      = int(bet * 5.5) if won else 0
    icon        = dice_emojis[result - 1]
    msg = f"{icon} Выпало **{result}**! {'🎉 Угадал! **x5.5** — +**' + str(payout) + ' 🪙**!' if won else f'💔 Промах. Ты ставил на {guess}.'}"
    return payout, msg

# ─── Валидация ────────────────────────────────────────────────────────────────

cooldowns: dict[str, float] = {}

async def validate(interaction: discord.Interaction, bet_str: str) -> tuple[int | None, dict | None]:
    user_id = str(interaction.user.id)
    now     = time.time()
    last    = cooldowns.get(user_id, 0)
    if now - last < COOLDOWN_SEC:
        ready_time = int(last + COOLDOWN_SEC)
        await interaction.response.send_message(
            f"⏱️ Подожди! Следующая ставка <t:{ready_time}:R>!", ephemeral=True
        )
        return None, None

    try:
        bet = int(bet_str.strip().replace(",", "").replace(" ", ""))
    except ValueError:
        await interaction.response.send_message("❌ Введи целое число!", ephemeral=True)
        return None, None

    if bet < MIN_BET:
        await interaction.response.send_message(f"❌ Минимальная ставка: **{MIN_BET} 🪙**", ephemeral=True)
        return None, None
    if bet > MAX_BET:
        await interaction.response.send_message(f"❌ Максимальная ставка: **{MAX_BET:,} 🪙**", ephemeral=True)
        return None, None

    user_data = await db.get_user(user_id)
    balance   = user_data.get("vibecoins", 0)
    if balance < bet:
        await interaction.response.send_message(
            f"❌ Не хватает **VibeКоинов**! У тебя **{balance:,} 🪙**, ставка **{bet:,} 🪙**.", ephemeral=True
        )
        return None, None

    cooldowns[user_id] = now
    return bet, user_data

async def apply_result(user_id: str, user_data: dict, bet: int, payout: int):
    """Списывает ставку, зачисляет выигрыш, обновляет БД."""
    balance = user_data.get("vibecoins", 0) - bet + payout
    await db.update_user(user_id, vibecoins=max(balance, 0))
    return max(balance, 0)

def result_color(payout: int, bet: int) -> int:
    if payout > bet:  return 0x2ECC71   # green
    if payout > 0:    return 0xF1C40F   # yellow
    return 0xE74C3C                      # red

# ─── Модалки ─────────────────────────────────────────────────────────────────

class SlotsModal(Modal, title="🎰 Слоты — Ставка"):
    bet_input = TextInput(
        label=f"Ставка ({MIN_BET}–{MAX_BET:,} 🪙)",
        placeholder="Введи сумму...",
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        bet, user_data = await validate(interaction, self.bet_input.value)
        if bet is None:
            return

        reels         = spin_slots()
        payout, line, footer = calc_slots(bet, reels)
        balance       = await apply_result(str(interaction.user.id), user_data, bet, payout)

        embed = discord.Embed(title="🎰 Слоты", color=result_color(payout, bet))
        embed.add_field(name="\u200b", value=f"## {line}", inline=False)
        embed.add_field(name="Результат", value=footer, inline=False)
        embed.set_footer(text=f"Ставка: {bet:,} 🪙  •  Баланс: {balance:,} 🪙")
        
        if interaction.message:
            menu_embed = interaction.message.embeds[0]
            await interaction.response.edit_message(embeds=[menu_embed, embed])
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


class CoinModal(Modal):
    bet_input = TextInput(
        label=f"Ставка ({MIN_BET}–{MAX_BET:,} 🪙)",
        placeholder="Введи сумму...",
        max_length=10
    )

    def __init__(self, choice: str):
        super().__init__(title=f"🪙 Ставка на {choice.capitalize()}")
        self.choice = choice

    async def on_submit(self, interaction: discord.Interaction):
        bet, user_data = await validate(interaction, self.bet_input.value)
        if bet is None:
            return

        payout, msg = flip_coin(bet, self.choice)
        balance     = await apply_result(str(interaction.user.id), user_data, bet, payout)

        embed = discord.Embed(title="🪙 Монетка", description=msg, color=result_color(payout, bet))
        embed.set_footer(text=f"Ставка: {bet:,} 🪙  •  Баланс: {balance:,} 🪙")
        
        if interaction.message:
            menu_embed = interaction.message.embeds[0]
            await interaction.response.edit_message(embeds=[menu_embed, embed])
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


class DiceModal(Modal):
    bet_input = TextInput(
        label=f"Ставка ({MIN_BET}–{MAX_BET:,} 🪙)",
        placeholder="Введи сумму...",
        max_length=10
    )

    def __init__(self, guess: int):
        super().__init__(title=f"🎲 Ставка на число {guess}")
        self.guess = guess

    async def on_submit(self, interaction: discord.Interaction):
        bet, user_data = await validate(interaction, self.bet_input.value)
        if bet is None:
            return

        payout, msg = roll_dice(bet, self.guess)
        balance     = await apply_result(str(interaction.user.id), user_data, bet, payout)

        embed = discord.Embed(title="🎲 Кости", description=msg, color=result_color(payout, bet))
        embed.set_footer(text=f"Ставка: {bet:,} 🪙  •  Баланс: {balance:,} 🪙")

        if interaction.message:
            menu_embed = interaction.message.embeds[0]
            await interaction.response.edit_message(embeds=[menu_embed, embed])
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


# ─── Главное меню казино ─────────────────────────────────────────────────────

class DiceSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Выбрать 1", emoji="1️⃣", value="1"),
            discord.SelectOption(label="Выбрать 2", emoji="2️⃣", value="2"),
            discord.SelectOption(label="Выбрать 3", emoji="3️⃣", value="3"),
            discord.SelectOption(label="Выбрать 4", emoji="4️⃣", value="4"),
            discord.SelectOption(label="Выбрать 5", emoji="5️⃣", value="5"),
            discord.SelectOption(label="Выбрать 6", emoji="6️⃣", value="6"),
        ]
        super().__init__(placeholder="🎲 Какое число выпадет? (x5.5)", options=options, custom_id="casino_dice_select")
        
    async def callback(self, interaction: discord.Interaction):
        guess = int(self.values[0])
        await interaction.response.send_modal(DiceModal(guess))

class CasinoView(View):
    """Persistent menu shown when using setup_casino."""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DiceSelect())

    @discord.ui.button(label="🎰 Слоты", style=discord.ButtonStyle.primary, custom_id="casino_slots")
    async def slots_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SlotsModal())

    @discord.ui.button(label="🦅 Орёл", style=discord.ButtonStyle.secondary, custom_id="casino_coin_heads")
    async def coin_h_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CoinModal("орёл"))

    @discord.ui.button(label="💿 Решка", style=discord.ButtonStyle.secondary, custom_id="casino_coin_tails")
    async def coin_t_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CoinModal("решка"))

    @discord.ui.button(label="❌ Выйти", style=discord.ButtonStyle.danger, custom_id="casino_leave")
    async def leave_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.channel.name.startswith("казино-"):
            await interaction.response.send_message("💣 Стол закрыт! Убираем фишки...", ephemeral=True)
            await asyncio.sleep(2)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("❌ Эту кнопку можно нажимать только в личном VIP-канале казино.", ephemeral=True)


# ─── Cog ─────────────────────────────────────────────────────────────────────

class Casino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="казик", aliases=["casino", "казино", "казинка"])
    @commands.has_permissions(administrator=True)
    async def setup_casino(self, ctx):
        """Создаёт постоянный embed казино с кнопками (только для админов)."""
        embed = discord.Embed(
            title="🎰 VibeКазино",
            description=(
                "Присаживайся за стол и умножай свои **VibeКоины**!\n\n"
                "**🎰 Слоты** — классика. 3 в ряд до **x50**, 2 слева = **x1.5**\n"
                "**🪙 Монетка** — 50/50. Угадай — получи **x1.9**\n"
                "**🎲 Кости** — угадай число 1–6 и получи **x5**!\n\n"
                f"Мин. ставка: **{MIN_BET} 🪙** • Макс: **{MAX_BET:,} 🪙**\n"
                f"Кулдаун между ставками: **{COOLDOWN_SEC} сек**"
            ),
            color=0xF1C40F
        )
        embed.set_image(url="https://media.giphy.com/media/3ohzdFmHSiRBbhzaE8/giphy.gif")
        embed.set_footer(text="Все результаты — случайные. Играй ответственно! 🍀")
        await ctx.send(embed=embed, view=CasinoView())
        await ctx.message.delete()

    @commands.hybrid_command(name="баланс", aliases=["balance", "монеты", "coins"])
    async def balance(self, ctx):
        """Показывает твой баланс VibeКоинов."""
        user_data = await db.get_user(str(ctx.author.id))
        balance   = user_data.get("vibecoins", 0)
        await ctx.send(f"🪙 Твой баланс: **{balance:,} VibeКоинов**", ephemeral=True)



async def setup(bot):
    await bot.add_cog(Casino(bot))
