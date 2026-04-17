import discord
from discord.ext import commands
from discord.ui import View, Button
from utils.db import db
from config import COLOR_MAIN
import asyncio
import random
import logging

def get_case_embed() -> discord.Embed:
    embed = discord.Embed(
        title="✨ Vibe Кейсы",
        description=(
            "🪵 **Дерево (100 🪙):** выигрыш от 10 до 500\n"
            "🪨 **Камень (300 🪙):** выигрыш от 50 до 1,200\n"
            "⚙️ **Железо (500 🪙):** выигрыш от 100 до 2,500\n"
            "📦 **Бронза (1,000 🪙):** выигрыш от 100 до 5,000\n"
            "💿 **Серебро (5,000 🪙):** выигрыш от 1,000 до 15,000\n"
            "🔮 **Нефрит (8,000 🪙):** выигрыш от 2,000 до 30,000\n"
            "🏵️ **Золото (10,000 🪙):** выигрыш от 3,000 до 40,000\n"
            "💎 **Бриллиант (50,000 🪙):** выигрыш от 10,000 до 250,000\n"
            "🟢 **Изумруд (100,000 🪙):** выигрыш от 25,000 до 600,000\n"
            "🔴 **Рубин (250,000 🪙):** выигрыш от 50,000 до 1,500,000\n"
            "🧿 **Сапфир (500,000 🪙):** выигрыш от 100,000 до 3,000,000\n"
            "🌌 **Vibe Ultimate (1,000,000 🪙):** выигрыш от 250,000 до 7,000,000\n\n"
            "Жми кнопку ниже, чтобы попытать удачу. Когда надоест - жми Выйти."
        ),
        color=COLOR_MAIN
    )
    embed.set_image(url="https://media1.tenor.com/m/Znt_b7v133IAAAAd/mystery-box.gif")
    return embed

class CaseView(View):
    def __init__(self, user_id=None):
        super().__init__(timeout=None)
        self.user_id = user_id

    async def _handle_case(self, interaction: discord.Interaction, price: int, min_val: int, max_val: int, case_name: str, emoji: str):
        # Если вью персистентная (из setup_hook), берем ID из автора взаимодействия
        uid = self.user_id if self.user_id else str(interaction.user.id)
        
        # В ветках проверка по названию
        if hasattr(interaction.channel, 'parent') and "┃кейс-" in interaction.channel.name:
            if str(interaction.user.id) not in interaction.channel.name:
                await interaction.response.send_message("Это не твой кейс!", ephemeral=True)
                return
        elif self.user_id and str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("Это не твой кейс!", ephemeral=True)
            return
        
        user_data = await db.get_user(uid)
        balance = user_data.get('vibecoins', 0)

        if balance < price:
            await interaction.response.send_message(f"❌ Не хватает **VibeКоинов** для {case_name}! У тебя {balance}/{price} 🪙", ephemeral=True)
            return

        # Снимаем деньги
        new_balance = balance - price
        cases_opened = user_data.get('cases_opened', 0) + 1
        await db.update_user(uid, vibecoins=new_balance, cases_opened=cases_opened)
        
        interaction.client.dispatch("case_opened", interaction.user, cases_opened)

        chance = random.randint(1, 100)
        
        if chance <= 60:  # 60% - Проигрыш (минус)
            win_amount = random.randint(min_val, max(min_val, price - 1))
        elif chance <= 80: # 20% - Окуп / Небольшой плюс
            upper = min(int(price * 1.5), max_val)
            win_amount = random.randint(price, max(price, upper))
        elif chance <= 90: # 10% - Нормальный плюс
            lower = min(int(price * 1.5) + 1, max_val)
            upper = min(int(price * 2.5), max_val)
            win_amount = random.randint(lower, max(lower, upper))
        elif chance <= 98: # 8% - Мега Выигрыш
            lower = min(int(price * 2.5) + 1, max_val)
            upper = min(int(price * 4.0), max_val)
            win_amount = random.randint(lower, max(lower, upper))
        else: # 2% - Джекпот
            lower = min(int(price * 4.0) + 1, max_val)
            win_amount = random.randint(lower, max(lower, max_val))

        # Отправляем начальное сообщение с анимацией
        embed = discord.Embed(title=f"{emoji} Открытие {case_name}...", description="[ 🎰 ] КРУТИМ РУЛЕТКУ [ 🎰 ]", color=discord.Color.blue())
        
        is_case_channel = interaction.message and "┃кейс-" in interaction.channel.name
        
        if is_case_channel:
            await interaction.response.send_message(embed=embed)
            try: await interaction.message.delete()
            except: pass
            msg = await interaction.original_response()
        else:
            await interaction.response.send_message(embed=embed)
            msg = await interaction.original_response()
        
        # Анимация "цифрового потока"
        steps = [random.randint(min_val, max_val) for _ in range(3)]
        
        for step_val in steps:
            await asyncio.sleep(0.4)
            embed.description = f"**[  {step_val:04d}  ]**"
            try:
                await msg.edit(embed=embed)
            except discord.HTTPException:
                pass

        await asyncio.sleep(0.3)

        # Финальный результат
        embed.title = f"{emoji} {case_name} открыт!"
        if win_amount > price:
            embed.color = discord.Color.green()
            embed.description = f"🎉 ОКУП! Выпало: **{win_amount} 🪙**\nТекущий баланс: **{new_balance + win_amount} 🪙**"
        else:
            embed.color = discord.Color.red()
            embed.description = f"📉 Минус... Выпало: **{win_amount} 🪙**\nТекущий баланс: **{new_balance + win_amount} 🪙**"

        await db.update_user(uid, vibecoins=new_balance + win_amount)
        try:
            await msg.edit(embed=embed)
        except:
            pass

        # Ресенд меню кейсов
        if is_case_channel:
            menu_embed = get_case_embed()
            await interaction.channel.send(content=interaction.user.mention, embed=menu_embed, view=CaseView(uid))

    @discord.ui.button(label="Дерево (100 🪙)", style=discord.ButtonStyle.secondary, emoji="🪵", row=0, custom_id="case_wood")
    async def btn_wooden(self, interaction: discord.Interaction, button: Button):
        await self._handle_case(interaction, 100, 10, 500, "Деревянного Кейса", "🪵")

    @discord.ui.button(label="Камень (300 🪙)", style=discord.ButtonStyle.secondary, emoji="🪨", row=0, custom_id="case_stone")
    async def btn_stone(self, interaction: discord.Interaction, button: Button):
        await self._handle_case(interaction, 300, 50, 1200, "Каменного Кейса", "🪨")

    @discord.ui.button(label="Железо (500 🪙)", style=discord.ButtonStyle.secondary, emoji="⚙️", row=0, custom_id="case_iron")
    async def btn_iron(self, interaction: discord.Interaction, button: Button):
        await self._handle_case(interaction, 500, 100, 2500, "Железного Кейса", "⚙️")

    @discord.ui.button(label="Бронза (1k 🪙)", style=discord.ButtonStyle.primary, emoji="📦", row=0, custom_id="case_bronze")
    async def btn_bronze(self, interaction: discord.Interaction, button: Button):
        await self._handle_case(interaction, 1000, 100, 5000, "Бронзового Кейса", "📦")

    @discord.ui.button(label="Серебро (5k 🪙)", style=discord.ButtonStyle.secondary, emoji="💿", row=0, custom_id="case_silver")
    async def btn_silver(self, interaction: discord.Interaction, button: Button):
        await self._handle_case(interaction, 5000, 1000, 15000, "Серебряного Кейса", "💿")

    @discord.ui.button(label="Нефрит (8k 🪙)", style=discord.ButtonStyle.secondary, emoji="🔮", row=1, custom_id="case_jade")
    async def btn_jade(self, interaction: discord.Interaction, button: Button):
        await self._handle_case(interaction, 8000, 2000, 30000, "Нефритового Кейса", "🔮")

    @discord.ui.button(label="Золото (10k 🪙)", style=discord.ButtonStyle.success, emoji="🏵️", row=1, custom_id="case_gold")
    async def btn_gold(self, interaction: discord.Interaction, button: Button):
        await self._handle_case(interaction, 10000, 3000, 40000, "Золотого Кейса", "🏵️")

    @discord.ui.button(label="Бриллиант (50k 🪙)", style=discord.ButtonStyle.primary, emoji="💎", row=1, custom_id="case_diamond")
    async def btn_diamond(self, interaction: discord.Interaction, button: Button):
        await self._handle_case(interaction, 50000, 10000, 250000, "Бриллиантового Кейса", "💎")

    @discord.ui.button(label="Изумруд (100k 🪙)", style=discord.ButtonStyle.secondary, emoji="🟢", row=1, custom_id="case_emerald")
    async def btn_emerald(self, interaction: discord.Interaction, button: Button):
        await self._handle_case(interaction, 100000, 25000, 600000, "Изумрудного Кейса", "🟢")

    @discord.ui.button(label="Рубин (250k 🪙)", style=discord.ButtonStyle.secondary, emoji="🔴", row=1, custom_id="case_ruby")
    async def btn_ruby(self, interaction: discord.Interaction, button: Button):
        await self._handle_case(interaction, 250000, 50000, 1500000, "Рубинового Кейса", "🔴")

    @discord.ui.button(label="Сапфир (500k 🪙)", style=discord.ButtonStyle.primary, emoji="🧿", row=2, custom_id="case_sapphire")
    async def btn_sapphire(self, interaction: discord.Interaction, button: Button):
        await self._handle_case(interaction, 500000, 100000, 3000000, "Сапфирового Кейса", "🧿")

    @discord.ui.button(label="Ultimate (1M 🪙)", style=discord.ButtonStyle.success, emoji="🌌", row=2, custom_id="case_ultimate")
    async def btn_ultimate(self, interaction: discord.Interaction, button: Button):
        await self._handle_case(interaction, 1000000, 250000, 7000000, "Vibe Ultimate Кейса", "🌌")

    @discord.ui.button(label="Выйти", style=discord.ButtonStyle.danger, emoji="🚪", row=2, custom_id="case_exit")
    async def btn_close(self, interaction: discord.Interaction, button: Button):
        uid = self.user_id if self.user_id else str(interaction.user.id)
        if str(interaction.user.id) != uid and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Только владелец комнаты или админ может её закрыть.", ephemeral=True)
            return

        await interaction.response.send_message("🚪 Закрываю комнату...")
        await asyncio.sleep(2)
        try:
            await interaction.channel.delete()
        except:
            pass

class Cases(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_create_vibe_case_room(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        thread_name = f"📦┃кейс-{interaction.user.name[:15]}"
        
        try:
            thread = await channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                auto_archive_duration=60
            )
            await thread.add_user(interaction.user)
            if interaction.guild.owner:
                await thread.add_user(interaction.guild.owner)
        except discord.Forbidden:
            await interaction.followup.send("❌ У бота нет прав на создание приватных веток.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)
            return

        await interaction.followup.send(f"✅ Комната создана в ветке: {thread.mention}", ephemeral=True)
        
        embed = get_case_embed()
        await thread.send(content=interaction.user.mention, embed=embed, view=CaseView(str(interaction.user.id)))

        async def _delete_thread():
            await asyncio.sleep(1800)
            try: await thread.delete()
            except: pass
        self.bot.loop.create_task(_delete_thread())

async def setup(bot):
    await bot.add_cog(Cases(bot))
