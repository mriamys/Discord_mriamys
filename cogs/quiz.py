import discord
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
import aiohttp
import html
import time
from utils.db import db

RUBQ_URL = "https://raw.githubusercontent.com/vladislavneon/RuBQ/master/RuBQ_2.0/RuBQ_2.0_test.json"
_questions_cache = []

async def load_quiz_database():
    global _questions_cache
    if _questions_cache: return True
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(RUBQ_URL, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    _questions_cache = [i for i in data if i.get('question_text') and i.get('answer_text')]
                    random.shuffle(_questions_cache)
                    return True
    except: pass
    return False

async def fetch_question():
    if not _questions_cache: await load_quiz_database()
    if _questions_cache:
        q = random.choice(_questions_cache)
        correct = q['answer_text']
        pool = [random.choice(_questions_cache)['answer_text'] for _ in range(10)]
        incorrect = [a for a in pool if a.lower() != correct.lower()][:3]
        while len(incorrect) < 3: incorrect.append("Неизвестно")
        return {"q": html.unescape(q['question_text']), "a": html.unescape(correct), "o": [html.unescape(a) for a in incorrect] + [html.unescape(correct)]}
    return {"q": "Как называется столица Франции?", "a": "Париж", "o": ["Марсель", "Лион", "Ницца", "Париж"]}

class QuizView(View):
    def __init__(self, bot, member, q_data):
        super().__init__(timeout=20.0)
        self.bot, self.member, self.q = bot, member, q_data
        self.message = None
        self.end_time = int(time.time() + 20)
        opts = list(self.q['o'])
        random.shuffle(opts)
        for opt in opts: self.add_item(QuizBtn(label=opt[:80], correct=opt == self.q['a']))
        self.add_item(Button(label="Закончить игру", style=discord.ButtonStyle.danger, custom_id="quiz_exit_btn", row=2))

    async def create_embed(self):
        user_data = await db.get_user(str(self.member.id))
        embed = discord.Embed(title="🌐 ВИКТОРИНА", description=f"**{self.q['q']}**", color=0x3498db)
        embed.add_field(name="⏰ Время", value=f"<t:{self.end_time}:R>", inline=True)
        embed.add_field(name="💰 Баланс", value=f"**{user_data['vibecoins']:,} 🪙**", inline=True)
        return embed

    async def on_timeout(self):
        for c in self.children: c.disabled = True
        try:
            if self.message:
                await self.message.edit(content=f"⏰ **ВРЕМЯ ВЫШЛО!** Ответ: `{self.q['a']}`", embed=None, view=self)
                await asyncio.sleep(3)
                await self._next_round()
        except: pass

    async def _next_round(self):
        user_data = await db.get_user(str(self.member.id))
        if user_data.get('vibecoins', 0) < 100:
            await self.message.channel.send(f"❌ {self.member.mention}, у тебя закончились коины для игры!"); return
        await db.update_user(str(self.member.id), vibecoins=user_data['vibecoins'] - 100)
        new_q = await fetch_question()
        new_v = QuizView(self.bot, self.member, new_q)
        new_msg = await self.message.channel.send(content=self.member.mention, embed=await new_v.create_embed(), view=new_v)
        new_v.message = new_msg

class QuizBtn(Button):
    def __init__(self, label, correct):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.correct = correct
    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if interaction.user.id != v.member.id: return
        v.stop()
        await interaction.response.defer()
        if self.correct:
            reward = random.randint(300, 600)
            data = await db.get_user(str(v.member.id))
            await db.update_user(str(v.member.id), vibecoins=data['vibecoins'] + reward)
            await interaction.edit_original_response(content=f"✅ **ВЕРНО!** +**{reward} 🪙**", embed=None, view=v)
        else:
            await interaction.edit_original_response(content=f"❌ **ОШИБКА!** Ответ: `{v.q['a']}`", embed=None, view=v)
        await asyncio.sleep(3); await v._next_round()

class QuizDuelView(View):
    def __init__(self, bot, p1, p2, bet, q):
        super().__init__(timeout=20.0)
        self.bot, self.players, self.bet, self.q = bot, [p1.id, p2.id], bet, q
        self.message = None
        self.end_time = int(time.time() + 20)
        opts = list(q['o'])
        random.shuffle(opts)
        for opt in opts: self.add_item(QuizDuelBtn(label=opt[:80], correct=opt == q['a']))

    async def create_embed(self):
        embed = discord.Embed(title="⚔️ БИТВА ЗНАТОКОВ", description=f"**{self.q['q']}**", color=0xe74c3c)
        embed.add_field(name="💰 Банк", value=f"**{self.bet * 2} 🪙**", inline=True)
        embed.add_field(name="⏰ Время", value=f"<t:{self.end_time}:R>", inline=True)
        return embed

    async def on_timeout(self):
        for c in self.children: c.disabled = True
        try:
            if self.message:
                await self.message.edit(content=f"⏰ **ВРЕМЯ ВЫШЛО!** Ответ: `{self.q['a']}`", embed=None, view=self)
                await asyncio.sleep(3)
                await self.message.channel.send(embed=discord.Embed(title="💡 ВИКТОРИНА", description="Никто не успел.", color=0x2ECC71), view=QuizRoomView(self.bot))
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
            w_data = await db.get_user(str(interaction.user.id))
            await db.update_user(str(interaction.user.id), vibecoins=w_data['vibecoins'] + v.bet * 2)
            await interaction.response.edit_message(content=f"🏆 **{interaction.user.mention} ВЫИГРАЛ {v.bet * 2} 🪙!**", embed=None, view=v)
            await asyncio.sleep(3); await interaction.channel.send(embed=discord.Embed(title="💡 ВИКТОРИНА", description="Играем еще?", color=0x2ECC71), view=QuizRoomView(self.bot))
        else:
            await interaction.response.send_message("❌ Неверно!", ephemeral=True)

class QuizRoomView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
    @discord.ui.button(label="💡 Соло (100 🪙)", style=discord.ButtonStyle.primary, custom_id="quiz_solo_btn")
    async def solo(self, interaction: discord.Interaction, button: Button):
        data = await db.get_user(str(interaction.user.id))
        if data.get('vibecoins', 0) < 100:
            await interaction.response.send_message("❌ Мало монет!", ephemeral=True); return
        await interaction.response.defer()
        await db.update_user(str(interaction.user.id), vibecoins=data['vibecoins'] - 100)
        q = await fetch_question()
        view = QuizView(self.bot, interaction.user, q)
        msg = await interaction.channel.send(content=interaction.user.mention, embed=await view.create_embed(), view=view)
        view.message = msg
        try: await interaction.message.delete()
        except: pass
    @discord.ui.button(label="⚔️ С другом (300 🪙)", style=discord.ButtonStyle.success, custom_id="quiz_duel_btn")
    async def invite(self, interaction: discord.Interaction, button: Button):
        data = await db.get_user(str(interaction.user.id))
        if data.get('vibecoins', 0) < 300:
            await interaction.response.send_message("❌ Нужно 300 монет!", ephemeral=True); return
        from cogs.shop import GameDuelSelectView
        await interaction.response.send_message("💡 Кого зовешь?", view=GameDuelSelectView(self.bot, interaction.user.id, 300, "quiz"), ephemeral=True)
    @discord.ui.button(label="❌ Закрыть", style=discord.ButtonStyle.danger, custom_id="quiz_close_btn")
    async def exit(self, interaction: discord.Interaction, button: Button):
        try: await interaction.channel.delete()
        except: pass

class Quiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(QuizRoomView(bot))
async def setup(bot): await bot.add_cog(Quiz(bot))
