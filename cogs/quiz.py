import discord
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
import aiohttp
import html
from utils.db import db

QUIZ_API_URL = "https://raw.githubusercontent.com/mriamys/trivia-base-ru/main/questions.json"

async def fetch_question():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(QUIZ_API_URL, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    q = random.choice(data)
                    return {
                        "q": html.unescape(q['question']),
                        "a": html.unescape(q['correct_answer']),
                        "o": [html.unescape(a) for a in q['incorrect_answers'][:3]] + [html.unescape(q['correct_answer'])]
                    }
    except: pass
    return {"q": "Как называется красная планета?", "a": "Марс", "o": ["Венера", "Марс", "Земля", "Плутон"]}

class QuizView(View):
    def __init__(self, bot, member, q_data):
        super().__init__(timeout=60)
        self.bot, self.member, self.q = bot, member, q_data
        opts = list(self.q['o'])
        random.shuffle(opts)
        for opt in opts:
            self.add_item(QuizBtn(label=opt[:80], correct=opt == self.q['a']))

class QuizBtn(Button):
    def __init__(self, label, correct):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.correct = correct

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if interaction.user.id != v.member.id: return
        for c in v.children: 
            c.disabled = True
            if hasattr(c, 'correct') and c.correct: c.style = discord.ButtonStyle.success
            elif c.label == self.label: c.style = discord.ButtonStyle.danger
        
        if self.correct:
            reward = random.randint(300, 600)
            data = await db.get_user(str(v.member.id))
            correct_count = data.get('quiz_correct', 0) + 1
            await db.update_user(str(v.member.id), vibecoins=data['vibecoins'] + reward, quiz_correct=correct_count)
            v.bot.dispatch("quiz_answered", v.member, True, correct_count)
            await interaction.response.edit_message(content=f"✅ **ВЕРНО!** Ты получил **{reward} 🪙**", view=v)
        else:
            await interaction.response.edit_message(content=f"❌ **ОШИБКА!** Правильный ответ: `{v.q['a']}`", view=v)
        
        await asyncio.sleep(3)
        desc = "**ПРАВИЛА:**\n🔹 Соло: вопрос из интернета, награда 300-600.\n🔹 Дуэль: кто первый ответил - тот забрал банк!\n\nВыбирай режим:"
        await interaction.channel.send(embed=discord.Embed(title="💡 ВИКТОРИНА", description=desc, color=0x2ECC71), view=QuizRoomView(v.bot))

class QuizDuelView(View):
    def __init__(self, bot, p1, p2, bet, q):
        super().__init__(timeout=60)
        self.bot, self.players, self.bet, self.q = bot, [p1.id, p2.id], bet, q
        opts = list(q['o'])
        random.shuffle(opts)
        for opt in opts: self.add_item(QuizDuelBtn(label=opt[:80], correct=opt == q['a']))

class QuizDuelBtn(Button):
    def __init__(self, label, correct):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.correct = correct

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if interaction.user.id not in v.players: return
        if self.correct:
            for c in v.children:
                c.disabled = True
                if hasattr(c, 'correct') and c.correct: c.style = discord.ButtonStyle.success
            w_data = await db.get_user(str(interaction.user.id))
            await db.update_user(str(interaction.user.id), vibecoins=w_data['vibecoins'] + v.bet * 2, quiz_correct=w_data.get('quiz_correct', 0) + 1)
            await interaction.response.edit_message(content=f"🏆 **{interaction.user.mention} ОТВЕТИЛ ПЕРВЫМ!** Банк: **{v.bet * 2} 🪙**", view=v)
            await asyncio.sleep(3)
            await interaction.channel.send(embed=discord.Embed(title="💡 ВИКТОРИНА", description="Битва окончена! Играем еще?", color=0x2ECC71), view=QuizRoomView(v.bot))
        else:
            await interaction.response.send_message("❌ Неверно! Ты выбываешь из этого раунда.", ephemeral=True)
            self.disabled, self.style = True, discord.ButtonStyle.danger
            await interaction.message.edit(view=v)

class QuizRoomView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="💡 Соло (100 🪙)", style=discord.ButtonStyle.primary, custom_id="quiz_solo_btn")
    async def solo(self, interaction: discord.Interaction, button: Button):
        data = await db.get_user(str(interaction.user.id))
        if data.get('vibecoins', 0) < 100:
            await interaction.response.send_message("❌ Мало денег!", ephemeral=True); return
        await interaction.response.defer()
        await db.update_user(str(interaction.user.id), vibecoins=data['vibecoins'] - 100)
        q = await fetch_question()
        await interaction.channel.send(content=f"{interaction.user.mention} 💡 **ВОПРОС:** {q['q']}", view=QuizView(self.bot, interaction.user, q))
        try: await interaction.message.delete()
        except: pass

    @discord.ui.button(label="⚔️ С другом (300 🪙)", style=discord.ButtonStyle.success, custom_id="quiz_duel_btn")
    async def invite(self, interaction: discord.Interaction, button: Button):
        from cogs.shop import GameDuelSelectView
        await interaction.response.send_message("💡 Выбери друга для битвы умов:", view=GameDuelSelectView(self.bot, interaction.user, 300, "quiz"), ephemeral=True)

    @discord.ui.button(label="❌ Закрыть", style=discord.ButtonStyle.danger, custom_id="quiz_close_btn")
    async def exit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🚪 Закрываю..."); await asyncio.sleep(2)
        try: await interaction.channel.delete()
        except: pass

class Quiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(QuizRoomView(bot))

async def setup(bot): await bot.add_cog(Quiz(bot))
