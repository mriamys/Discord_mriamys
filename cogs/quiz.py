import discord
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
import aiohttp
import html
import time
from utils.db import db

# Ссылка на обновляемую базу вопросов (RAW JSON)
# Этот файл содержит более 1000 проверенных вопросов на русском языке
QUIZ_REMOTE_URL = "https://raw.githubusercontent.com/mriamys/trivia-base-ru/main/questions.json"

async def fetch_question():
    """Скачивает случайный вопрос из интернета в реальном времени."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(QUIZ_REMOTE_URL, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Берем абсолютно случайный вопрос из интернет-базы
                    q_data = random.choice(data)
                    
                    return {
                        "q": html.unescape(q_data['question']),
                        "a": html.unescape(q_data['correct_answer']),
                        "o": [html.unescape(a) for a in q_data['incorrect_answers'][:3]] + [html.unescape(q_data['correct_answer'])]
                    }
    except Exception as e:
        print(f"Quiz Internet Error: {e}")
    
    # Фолбэк если интернет пропал или сайт недоступен
    return {"q": "Как называется красная планета?", "a": "Марс", "o": ["Венера", "Марс", "Земля", "Плутон"]}

class QuizView(View):
    def __init__(self, bot, member, q_data):
        super().__init__(timeout=20.0)
        self.bot, self.member, self.q = bot, member, q_data
        self.message = None
        self.end_time = int(time.time() + 20)
        
        opts = list(self.q['o'])
        random.shuffle(opts)
        for opt in opts:
            self.add_item(QuizBtn(label=opt[:80], correct=opt == self.q['a']))
        
        exit_btn = Button(label="Закончить игру", style=discord.ButtonStyle.danger, row=2)
        exit_btn.callback = self._exit_callback
        self.add_item(exit_btn)

    async def on_timeout(self):
        for c in self.children: c.disabled = True
        try:
            if self.message:
                await self.message.edit(content=f"⏰ **ВРЕМЯ ВЫШЛО!**\nПравильный ответ: `{self.q['a']}`", view=self)
                await asyncio.sleep(3)
                await self._next_round()
        except: pass

    async def _next_round(self):
        # При каждом вызове лезем в интернет за новым вопросом
        new_q = await fetch_question()
        new_v = QuizView(self.bot, self.member, new_q)
        content = f"{self.member.mention} 💡 **НОВЫЙ ВОПРОС ИЗ СЕТИ:**\n**{new_q['q']}**\n\n⏰ Время выйдет: <t:{new_v.end_time}:R>"
        new_msg = await self.message.channel.send(content=content, view=new_v)
        new_v.message = new_msg

    async def _exit_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id: return
        self.stop()
        await interaction.response.send_message("👋 Викторина окончена!")
        await asyncio.sleep(1)
        desc = "**Режимы:**\n🔹 Соло: вопросы из интернета.\n🔹 Дуэль: битва на скорость!"
        await interaction.channel.send(embed=discord.Embed(title="💡 ВИКТОРИНА", description=desc, color=0x2ECC71), view=QuizRoomView(self.bot))

class QuizBtn(Button):
    def __init__(self, label, correct):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.correct = correct

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if interaction.user.id != v.member.id: return
        v.stop() 
        await interaction.response.defer()
        
        for c in v.children: 
            if isinstance(c, Button) and c.label != "Закончить игру":
                c.disabled = True
                if hasattr(c, 'correct') and c.correct: c.style = discord.ButtonStyle.success
                elif c.label == self.label: c.style = discord.ButtonStyle.danger
        
        if self.correct:
            reward = random.randint(300, 600)
            data = await db.get_user(str(v.member.id))
            await db.update_user(str(v.member.id), vibecoins=data['vibecoins'] + reward, quiz_correct=data.get('quiz_correct', 0) + 1)
            await interaction.edit_original_response(content=f"✅ **ВЕРНО!** Получено **{reward} 🪙**", view=v)
        else:
            await interaction.edit_original_response(content=f"❌ **ОШИБКА!** Правильный ответ: `{v.q['a']}`", view=v)
        
        await asyncio.sleep(3)
        await v._next_round()

class QuizDuelView(View):
    def __init__(self, bot, p1, p2, bet, q):
        super().__init__(timeout=20.0)
        self.bot, self.players, self.bet, self.q = bot, [p1.id, p2.id], bet, q
        self.message = None
        self.end_time = int(time.time() + 20)
        
        opts = list(q['o'])
        random.shuffle(opts)
        for opt in opts: self.add_item(QuizDuelBtn(label=opt[:80], correct=opt == q['a']))

    async def on_timeout(self):
        for c in self.children: c.disabled = True
        try:
            if self.message:
                await self.message.edit(content=f"⏰ **ВРЕМЯ ВЫШЛО!** Ответ был: `{self.q['a']}`", view=self)
                await asyncio.sleep(3)
                await self.message.channel.send(embed=discord.Embed(title="💡 ВИКТОРИНА", description="Никто не успел ответить.", color=0x2ECC71), view=QuizRoomView(self.bot))
        except: pass

class QuizDuelBtn(Button):
    def __init__(self, label, correct):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.correct = correct

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if interaction.user.id not in v.players: return
        if self.correct:
            v.stop()
            for c in v.children:
                c.disabled = True
                if hasattr(c, 'correct') and c.correct: c.style = discord.ButtonStyle.success
            w_data = await db.get_user(str(interaction.user.id))
            await db.update_user(str(interaction.user.id), vibecoins=w_data['vibecoins'] + v.bet * 2, quiz_correct=w_data.get('quiz_correct', 0) + 1)
            await interaction.response.edit_message(content=f"🏆 **{interaction.user.mention} ПЕРВЫЙ!** Банк: **{v.bet * 2} 🪙**", view=v)
            await asyncio.sleep(3)
            await interaction.channel.send(embed=discord.Embed(title="💡 ВИКТОРИНА", description="Битва окончена!", color=0x2ECC71), view=QuizRoomView(self.bot))
        else:
            await interaction.response.send_message("❌ Неправильно! Ты выбыл.", ephemeral=True)
            self.disabled, self.style = True, discord.ButtonStyle.danger
            await interaction.message.edit(view=v)

class QuizRoomView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="💡 Играть Соло (100 🪙)", style=discord.ButtonStyle.primary, custom_id="quiz_solo_v9")
    async def solo(self, interaction: discord.Interaction, button: Button):
        data = await db.get_user(str(interaction.user.id))
        if data.get('vibecoins', 0) < 100:
            await interaction.response.send_message("❌ Мало монет!", ephemeral=True); return
        await interaction.response.defer()
        await db.update_user(str(interaction.user.id), vibecoins=data['vibecoins'] - 100)
        # Первый вопрос из сети
        q = await fetch_question()
        view = QuizView(self.bot, interaction.user, q)
        msg = await interaction.channel.send(content=f"{interaction.user.mention} 💡 **ВОПРОС ИЗ ИНТЕРНЕТА:**\n**{q['q']}**\n\n⏰ Время выйдет: <t:{view.end_time}:R>", view=view)
        view.message = msg
        try: await interaction.message.delete()
        except: pass

    @discord.ui.button(label="⚔️ С другом (300 🪙)", style=discord.ButtonStyle.success, custom_id="quiz_duel_v9")
    async def invite(self, interaction: discord.Interaction, button: Button):
        from cogs.shop import GameDuelSelectView
        await interaction.response.send_message("💡 Выбери друга для битвы умов:", view=GameDuelSelectView(self.bot, interaction.user.id, 300, "quiz"), ephemeral=True)

    @discord.ui.button(label="❌ Закрыть руму", style=discord.ButtonStyle.danger, custom_id="quiz_close_v9")
    async def exit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🚪 Комната закрывается..."); await asyncio.sleep(2)
        try: await interaction.channel.delete()
        except: pass

class Quiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(QuizRoomView(bot))

async def setup(bot): await bot.add_cog(Quiz(bot))
