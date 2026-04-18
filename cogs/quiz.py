import discord
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
import aiohttp
import html
from utils.db import db

# Источник вопросов (большая база на русском языке)
QUIZ_API_URL = "https://raw.githubusercontent.com/mriamys/trivia-base-ru/main/questions.json"

async def fetch_question():
    """Загружает случайный вопрос из интернета."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(QUIZ_API_URL, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    question_data = random.choice(data)
                    return {
                        "q": html.unescape(question_data['question']),
                        "a": html.unescape(question_data['correct_answer']),
                        "o": [html.unescape(a) for a in question_data['incorrect_answers'][:3]] + [html.unescape(question_data['correct_answer'])]
                    }
    except Exception as e:
        print(f"Quiz API Error: {e}")
        return {
            "q": "Как называется планета, которую называют 'красной'?",
            "a": "Марс",
            "o": ["Венера", "Марс", "Юпитер", "Сатурн"]
        }

class QuizView(View):
    def __init__(self, bot, member, question_data):
        super().__init__(timeout=30)
        self.bot = bot
        self.member = member
        self.q = question_data
        
        options = list(self.q['o'])
        random.shuffle(options)
        
        for option in options:
            self.add_item(QuizButton(label=option[:80], style=discord.ButtonStyle.secondary, correct=option == self.q['a']))

class QuizButton(Button):
    def __init__(self, label, style, correct):
        super().__init__(label=label, style=style)
        self.correct = correct

    async def callback(self, interaction: discord.Interaction):
        view: QuizView = self.view
        if interaction.user.id != view.member.id: return
        
        for child in view.children:
            if isinstance(child, Button): child.disabled = True
            if hasattr(child, 'correct') and child.correct: child.style = discord.ButtonStyle.success
            elif child.label == self.label: child.style = discord.ButtonStyle.danger
                
        if self.correct:
            reward = random.randint(300, 600)
            user_data = await db.get_user(str(view.member.id))
            correct_count = user_data.get('quiz_correct', 0) + 1
            await db.update_user(str(view.member.id), vibecoins=user_data.get('vibecoins', 0) + reward, quiz_correct=correct_count)
            view.bot.dispatch("quiz_answered", view.member, True, correct_count)
            await interaction.response.edit_message(content=f"✅ **Правильно!** Это был `{view.q['a']}`.\nТы получил **{reward} 🪙**", view=view)
        else:
            user_data = await db.get_user(str(view.member.id))
            correct_count = user_data.get('quiz_correct', 0)
            view.bot.dispatch("quiz_answered", view.member, False, correct_count)
            await interaction.response.edit_message(content=f"❌ **Неверно!** Правильный ответ: `{view.q['a']}`.", view=view)

# ─── ДУЭЛЬ ВИКТОРИНА ──────────────────────────────────────────────────────────

class QuizDuelView(View):
    def __init__(self, bot, p1, p2, bet, question_data):
        super().__init__(timeout=60)
        self.bot = bot
        self.players = [p1.id, p2.id]
        self.bet = bet
        self.q = question_data
        self.winner = None
        
        options = list(self.q['o'])
        random.shuffle(options)
        
        for option in options:
            self.add_item(QuizDuelButton(label=option[:80], correct=option == self.q['a']))

class QuizDuelButton(Button):
    def __init__(self, label, correct):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.correct = correct

    async def callback(self, interaction: discord.Interaction):
        view: QuizDuelView = self.view
        if interaction.user.id not in view.players: return
        
        if self.correct:
            # Кто первый нажал — тот победил
            view.winner = interaction.user
            for child in view.children:
                child.disabled = True
                if hasattr(child, 'correct') and child.correct: child.style = discord.ButtonStyle.success
            
            # Начисляем банк
            w_data = await db.get_user(str(view.winner.id))
            correct_count = w_data.get('quiz_correct', 0) + 1
            await db.update_user(str(view.winner.id), vibecoins=w_data.get('vibecoins', 0) + view.bet * 2, quiz_correct=correct_count)
            view.bot.dispatch("quiz_answered", view.winner, True, correct_count)
            
            await interaction.response.edit_message(
                content=f"🏆 **{view.winner.mention} ответил ПЕРВЫМ и забирает {view.bet * 2} 🪙!**\nПравильный ответ: `{view.q['a']}`",
                view=view
            )
        else:
            # Игрок ошибся — он выбывает из этого раунда
            await interaction.response.send_message("❌ Неверно! Ты больше не можешь отвечать в этой дуэли.", ephemeral=True)
            # Если оба ошиблись — ничья
            # Для простоты: просто блокируем кнопку для него
            self.disabled = True
            self.style = discord.ButtonStyle.danger
            await interaction.message.edit(view=view)

class QuizRoomView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="💡 Соло Викторина (100 🪙)", style=discord.ButtonStyle.primary)
    async def solo(self, interaction: discord.Interaction, button: Button):
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < 100:
            await interaction.response.send_message("❌ Недостаточно VibeКоинов!", ephemeral=True)
            return
            
        new_bal = user_data.get('vibecoins', 0) - 100
        await db.update_user(str(interaction.user.id), vibecoins=new_bal)
        self.bot.dispatch("balance_updated", interaction.user, new_bal)
        
        await interaction.response.defer()
        q = await fetch_question()
        view = QuizView(self.bot, interaction.user, q)
        await interaction.followup.send(f"💡 **ВОПРОС:** {q['q']}", view=view)

    @discord.ui.button(label="⚔️ Битва Знатоков (300 🪙)", style=discord.ButtonStyle.success)
    async def invite(self, interaction: discord.Interaction, button: Button):
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < 300:
            await interaction.response.send_message("❌ Недостаточно VibeКоинов!", ephemeral=True)
            return
            
        from cogs.shop import GameDuelSelectView
        await interaction.response.send_message("💡 Выбери оппонента для Битвы Знатоков:", view=GameDuelSelectView(self.bot, interaction.user, 300, "quiz"), ephemeral=True)

    @discord.ui.button(label="❌ Выйти", style=discord.ButtonStyle.danger)
    async def exit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("👋 Комната викторины закрыта.")
        await asyncio.sleep(3)
        try: await interaction.channel.delete()
        except: pass

class Quiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(Quiz(bot))
