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
WEIGHTS      = [ 40,   30,   20,   12,    8,    5,    2,    1]

def spin_slots():
    return random.choices(SYMBOLS, weights=WEIGHTS, k=3)

def calc_slots(bet: int, reels: list) -> tuple[int, str, str]:
    """(payout, result_line, footer)"""
    a, b, c = reels
    line = f"[ {a}  {b}  {c} ]"
    
    if a == b == c:
        mults = {"7️⃣": 50.0, "💎": 25.0, "⭐": 15.0, "🔔": 10.0,
                 "🍇": 5.0,  "🍊": 4.0, "🍋": 3.0, "🍒": 2.0}
        mult = mults.get(a, 2.0)
        payout = int(bet * mult)
        msg = f"🎰 **ДЖЕКПОТ!!!** x{mult:.0f}" if mult >= 15 else f"✨ **Три в ряд!** x{mult:.0f}"
        return payout, line, f"{msg} — выигрыш **{payout:,} 🪙**!"
    
    elif a == b:
        payout = int(bet * 1.5)
        return payout, line, f"🎯 Два совпадения слева — x1.5 — выигрыш **{payout:,} 🪙**"
    
    elif a == "🍒":
        payout = int(bet * 0.5)
        return payout, line, f"🍒 Первая вишенка спасает! Утешительный возврат: **{payout:,} 🪙**"
        
    return 0, line, "❌ Мимо! Попробуй ещё раз."


def flip_coin(bet: int, choice: str) -> tuple[int, str]:
    result = random.choice(["Орёл", "Решка"])
    icons  = {"Орёл": "🦅", "Решка": "💿"}
    won    = result.lower() == choice.lower()
    payout = int(bet * 1.9) if won else 0
    icon   = icons[result]
    msg    = f"{icon} Выпало **{result}**! {'🥳 Победа! +**' + str(payout) + ' 🪙**' if won else '💔 Проигрыш.'}"
    return payout, msg

def roll_dice(bet: int, guess: int) -> tuple[int, str]:
    result      = random.randint(1, 6)
    dice_emojis = ["⚀","⚁","⚂","⚃","⚄","⚅"]
    won         = result == guess
    payout      = int(bet * 5.0) if won else 0
    icon        = dice_emojis[result - 1]
    msg = f"{icon} Выпало **{result}**! {'🎉 Угадал! x5 — +**' + str(payout) + ' 🪙**!' if won else f'💔 Промах. Ты ставил на {guess}.'}"
    return payout, msg

# ─── Валидация ────────────────────────────────────────────────────────────────

cooldowns: dict[str, float] = {}

async def validate(interaction: discord.Interaction, bet_str: str) -> tuple[int | None, dict | None]:
    user_id = str(interaction.user.id)
    now     = time.time()
    last    = cooldowns.get(user_id, 0)
    if now - last < COOLDOWN_SEC:
        remaining = int(COOLDOWN_SEC - (now - last))
        await interaction.response.send_message(
            f"⏱️ Подожди ещё **{remaining} сек** перед следующей ставкой!", ephemeral=True
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
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CoinModal(Modal, title="🪙 Монетка — Ставка"):
    bet_input = TextInput(
        label=f"Ставка ({MIN_BET}–{MAX_BET:,} 🪙)",
        placeholder="Введи сумму...",
        max_length=10
    )
    choice_input = TextInput(
        label="Орёл или Решка?",
        placeholder="орёл / решка",
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        choice = self.choice_input.value.strip().lower()
        if choice not in ("орёл", "решка", "orel", "reshka"):
            await interaction.response.send_message("❌ Напиши **орёл** или **решка**!", ephemeral=True)
            return

        # normalize English aliases
        choice = "орёл" if choice in ("орёл", "orel") else "решка"

        bet, user_data = await validate(interaction, self.bet_input.value)
        if bet is None:
            return

        payout, msg = flip_coin(bet, choice)
        balance     = await apply_result(str(interaction.user.id), user_data, bet, payout)

        embed = discord.Embed(title="🪙 Монетка", description=msg, color=result_color(payout, bet))
        embed.set_footer(text=f"Ставка: {bet:,} 🪙  •  Баланс: {balance:,} 🪙")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class DiceModal(Modal, title="🎲 Кости — Ставка"):
    bet_input = TextInput(
        label=f"Ставка ({MIN_BET}–{MAX_BET:,} 🪙)",
        placeholder="Введи сумму...",
        max_length=10
    )
    guess_input = TextInput(
        label="Угадай число (1–6) — выигрыш x5!",
        placeholder="1, 2, 3, 4, 5 или 6",
        max_length=1
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            guess = int(self.guess_input.value.strip())
            if not 1 <= guess <= 6:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Число должно быть от 1 до 6!", ephemeral=True)
            return

        bet, user_data = await validate(interaction, self.bet_input.value)
        if bet is None:
            return

        payout, msg = roll_dice(bet, guess)
        balance     = await apply_result(str(interaction.user.id), user_data, bet, payout)

        embed = discord.Embed(title="🎲 Кости", description=msg, color=result_color(payout, bet))
        embed.set_footer(text=f"Ставка: {bet:,} 🪙  •  Баланс: {balance:,} 🪙")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ─── Главное меню казино ─────────────────────────────────────────────────────

class CasinoView(View):
    """Persistent menu shown when using setup_casino."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎰 Слоты", style=discord.ButtonStyle.primary, custom_id="casino_slots")
    async def slots_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SlotsModal())

    @discord.ui.button(label="🪙 Монетка", style=discord.ButtonStyle.secondary, custom_id="casino_coin")
    async def coin_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CoinModal())

    @discord.ui.button(label="🎲 Кости", style=discord.ButtonStyle.success, custom_id="casino_dice")
    async def dice_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(DiceModal())


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
