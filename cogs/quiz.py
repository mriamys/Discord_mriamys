import discord
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
import aiohttp
import html
import time
from utils.db import db

# Огромная интернет-база (3000+ вопросов)
RUBQ_URL = "https://raw.githubusercontent.com/vladislavneon/RuBQ/master/RuBQ_2.0/RuBQ_2.0_dev.json"

# Кэш и настройки
_questions_cache = []
_used_indices = set()

async def load_quiz_database():
    """Загружает всю базу вопросов из интернета один раз."""
    global _questions_cache
    if _questions_cache: return True
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(RUBQ_URL, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        _questions_cache = data
                        random.shuffle(_questions_cache)
                        return True
    except Exception as e:
        print(f"Quiz Heavy Load Error: {e}")
    return False

async def fetch_question():
    """Берет случайный вопрос из уже загруженного кэша."""
    global _questions_cache, _used_indices
    
    if not _questions_cache:
        success = await load_quiz_database()
        if not success: return None
        
    attempts = 0
    while attempts < 100:
        q_item = random.choice(_questions_cache)
        idx = _questions_cache.index(q_item)
        
        if idx not in _used_indices:
            _used_indices.add(idx)
            if len(_used_indices) > 2000: _used_indices.clear()
            
            q_text = q_item.get('question_text', '')
            correct_ans = q_item.get('answer_text', '')
            
            if not q_text or not correct_ans: continue
            
            # Подбор ложных ответов
            incorrect = []
            while len(incorrect) < 3:
                fake = random.choice(_questions_cache).get('answer_text', '...')
                if fake.lower() != correct_ans.lower() and fake not in incorrect:
                    incorrect.append(fake)
                    
            return {
                "q": html.unescape(q_text),
                "a": html.unescape(correct_ans),
                "o": [html.unescape(a) for a in incorrect] + [html.unescape(correct_ans)]
            }
        attempts += 1
    return None

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

    def create_embed(self):
        embed = discord.Embed(title="🌐 МЕГА-ВИКТОРИНА", description=f"**{self.q['q']}**", color=0x3498db)
        embed.add_field(name="⏰ Время на ответ", value=f"<t:{self.end_time}:R>", inline=True)
        embed.set_footer(text=f"Игрок: {self.member.display_name} | База: 3000+ вопросов")
        return embed

    async def on_timeout(self):
        for c in self.children: c.disabled = True
        try:
            if self.message:
                await self.message.edit(content=f"⏰ **ВРЕМЯ ВЫШЛО!** Правильный ответ: `{self.q['a']}`", embed=None, view=self)
                await asyncio.sleep(3)
                await self._next_round()
        except: pass

    async def _next_round(self):
        new_q = await fetch_question()
        if not new_q: return
        new_v = QuizView(self.bot, self.member, new_q)
        new_msg = await self.message.channel.send(content=self.member.mention, embed=new_v.create_embed(), view=new_v)
        new_v.message = new_msg

    async def _exit_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id: return
        self.stop()
        await interaction.response.send_message("👋 Викторина окончена!", ephemeral=True)
        desc = "**Выбирай режим:**\n🔹 Соло: случайные интернет-вопросы.\n🔹 Дуэль: битва на скорость!"
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
            await interaction.edit_original_response(content=f"✅ **ВЕРНО!** +**{reward} 🪙**", embed=None, view=v)
        else:
            await interaction.edit_original_response(content=f"❌ **ОШИБКА!** Правильный ответ: `{v.q['a']}`", embed=None, view=v)
        
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

    def create_embed(self):
        embed = discord.Embed(title="⚔️ БИТВА ЗНАТОКОВ", description=f"**{self.q['q']}**", color=0xe74c3c)
        embed.add_field(name="💰 Банк", value=f"**{self.bet * 2} 🪙**", inline=True)
        embed.add_field(name="⏰ Время", value=f"<t:{self.end_time}:R>", inline=True)
        return embed

    async def on_timeout(self):
        for c in self.children: c.disabled = True
        try:
            if self.message:
                await self.message.edit(content=f"⏰ **ВРЕМЯ ВЫШЛО!** Никто не ответил. Ответ: `{self.q['a']}`", embed=None, view=self)
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
            for c in v.children:
                c.disabled = True
                if hasattr(c, 'correct') and c.correct: c.style = discord.ButtonStyle.success
            w_data = await db.get_user(str(interaction.user.id))
            await db.update_user(str(interaction.user.id), vibecoins=w_data['vibecoins'] + v.bet * 2, quiz_correct=w_data.get('quiz_correct', 0) + 1)
            await interaction.response.edit_message(content=f"🏆 **{interaction.user.mention} ВЫИГРАЛ {v.bet * 2} 🪙!**", embed=None, view=v)
            await asyncio.sleep(3)
            await interaction.channel.send(embed=discord.Embed(title="💡 ВИКТОРИНА", description="Хотите еще битву?", color=0x2ECC71), view=QuizRoomView(self.bot))
        else:
            await interaction.response.send_message("❌ Неправильно! Ты выбываешь.", ephemeral=True)
            self.disabled, self.style = True, discord.ButtonStyle.danger
            await interaction.message.edit(view=v)

class QuizRoomView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="💡 Играть Соло (100 🪙)", style=discord.ButtonStyle.primary, custom_id="quiz_solo_v14")
    async def solo(self, interaction: discord.Interaction, button: Button):
        data = await db.get_user(str(interaction.user.id))
        if data.get('vibecoins', 0) < 100:
            await interaction.response.send_message("❌ Мало монет!", ephemeral=True); return
        await interaction.response.defer()
        await db.update_user(str(interaction.user.id), vibecoins=data['vibecoins'] - 100)
        q = await fetch_question()
        if not q:
            await interaction.followup.send("❌ Ошибка загрузки базы. Попробуй через минуту.", ephemeral=True); return
        view = QuizView(self.bot, interaction.user, q)
        msg = await interaction.channel.send(content=interaction.user.mention, embed=view.create_embed(), view=view)
        view.message = msg
        try: await interaction.message.delete()
        except: pass

    @discord.ui.button(label="⚔️ С другом (300 🪙)", style=discord.ButtonStyle.success, custom_id="quiz_duel_v14")
    async def invite(self, interaction: discord.Interaction, button: Button):
        from cogs.shop import GameDuelSelectView
        await interaction.response.send_message("💡 Выбери друга для битвы умов:", view=GameDuelSelectView(self.bot, interaction.user.id, 300, "quiz"), ephemeral=True)

    @discord.ui.button(label="❌ Закрыть руму", style=discord.ButtonStyle.danger, custom_id="quiz_close_v14")
    async def exit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🚪 Комната закрывается..."); await asyncio.sleep(2)
        try: await interaction.channel.delete()
        except: pass

class Quiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(QuizRoomView(bot))

async def setup(bot): await bot.add_cog(Quiz(bot))
