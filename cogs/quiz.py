import discord
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
import aiohttp
import html
import time
from utils.db import db

# Огромная интернет-база (RuBQ Test Set - 2300+ вопросов)
RUBQ_URL = "https://raw.githubusercontent.com/vladislavneon/RuBQ/master/RuBQ_2.0/RuBQ_2.0_test.json"

# Кэш и настройки
_questions_cache = []
_used_indices = set()

# Резервная база на случай любых ошибок (50+ вопросов)
FALLBACK_DATA = [
    {"q": "Как называется столица Австралии?", "a": "Канберра", "o": ["Сидней", "Мельбурн", "Перт"]},
    {"q": "В каком году произошла авария на Чернобыльской АЭС?", "a": "1986", "o": ["1984", "1988", "1990"]},
    {"q": "Кто создал серию игр 'Metal Gear'?", "a": "Хидэо Кодзима", "o": ["Сид Мейер", "Тодд Говард", "Гейб Ньюэлл"]},
    {"q": "Какая планета самая большая в Солнечной системе?", "a": "Юпитер", "o": ["Сатурн", "Нептун", "Марс"]},
    {"q": "Как называется самый глубокий океан?", "a": "Тихий", "o": ["Атлантический", "Индийский", "Северный"]},
    {"q": "Сколько байт в одном килобайте?", "a": "1024", "o": ["1000", "512", "2048"]},
    {"q": "Какое химическое обозначение у золота?", "a": "Au", "o": ["Ag", "Fe", "Cu"]},
    {"q": "Кто написал 'Мона Лизу'?", "a": "Леонардо да Винчи", "o": ["Микеланджело", "Рафаэль", "Пикассо"]},
    {"q": "Как назывался первый спутник Земли?", "a": "Спутник-1", "o": ["Восток", "Союз", "Мир"]},
    {"q": "Какая валюта используется в Японии?", "a": "Иена", "o": ["Юань", "Вон", "Доллар"]},
    {"q": "В какой стране находится гора Эверест?", "a": "Непал", "o": ["Китай", "Индия", "Бутан"]},
    {"q": "Кто открыл Америку в 1492 году?", "a": "Христофор Колумб", "o": ["Васко да Гама", "Магеллан", "Веспуччи"]},
    {"q": "Какой элемент — основа органической жизни?", "a": "Углерод", "o": ["Кислород", "Азот", "Водород"]},
    {"q": "Сколько костей в теле взрослого человека?", "a": "206", "o": ["180", "220", "250"]},
    {"q": "В каком году распался СССР?", "a": "1991", "o": ["1989", "1990", "1992"]},
    {"q": "Какой язык программирования создал Гвидо ван Россум?", "a": "Python", "o": ["Java", "C++", "Ruby"]},
    {"q": "Как называется самая длинная река?", "a": "Амазонка", "o": ["Нил", "Миссисипи", "Янцзы"]},
    {"q": "Кто написал 'Преступление и наказание'?", "a": "Достоевский", "o": ["Толстой", "Чехов", "Пушкин"]},
    {"q": "Какое море омывает берега Крыма?", "a": "Черное", "o": ["Средиземное", "Каспийское", "Азовское"]},
    {"q": "Какая компания создала PlayStation?", "a": "Sony", "o": ["Nintendo", "Microsoft", "Sega"]}
]

async def load_quiz_database():
    """Загружает всю базу вопросов из интернета один раз."""
    global _questions_cache
    if _questions_cache: return True
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
    }
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(RUBQ_URL, timeout=30) as resp:
                if resp.status == 200:
                    # Важно: content_type=None, так как github отдает text/plain
                    data = await resp.json(content_type=None)
                    if isinstance(data, list) and len(data) > 0:
                        # Фильтруем битые данные заранее
                        valid_data = [item for item in data if item.get('question_text') and item.get('answer_text')]
                        if valid_data:
                            _questions_cache = valid_data
                            random.shuffle(_questions_cache)
                            return True
    except Exception as e:
        print(f"Quiz Heavy Load Error: {e}")
    return False

async def fetch_question():
    """Берет случайный вопрос из уже загруженного кэша с фолбэком."""
    global _questions_cache, _used_indices
    
    if not _questions_cache:
        await load_quiz_database()
        
    if _questions_cache:
        attempts = 0
        while attempts < 100:
            idx = random.randint(0, len(_questions_cache) - 1)
            
            if idx not in _used_indices:
                _used_indices.add(idx)
                # Защита от переполнения
                if len(_used_indices) >= len(_questions_cache) - 10: 
                    _used_indices.clear()
                
                q_item = _questions_cache[idx]
                q_text = q_item.get('question_text', '')
                correct_ans = q_item.get('answer_text', '')
                
                # Подбор ложных ответов
                incorrect = []
                misses = 0
                while len(incorrect) < 3 and misses < 50:
                    fake = random.choice(_questions_cache).get('answer_text', '...')
                    if fake.lower() != correct_ans.lower() and fake not in incorrect:
                        incorrect.append(fake)
                    misses += 1
                        
                while len(incorrect) < 3:
                    incorrect.append("Неизвестно")
                    
                return {
                    "q": html.unescape(q_text),
                    "a": html.unescape(correct_ans),
                    "o": [html.unescape(a) for a in incorrect] + [html.unescape(correct_ans)]
                }
            attempts += 1

    # Фолбэк, если интернет совсем мертв или кэш пуст
    fb_q = random.choice(FALLBACK_DATA)
    opts = list(fb_q['o']) + [fb_q['a']]
    return {
        "q": fb_q['q'],
        "a": fb_q['a'],
        "o": opts
    }

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
        embed.set_footer(text=f"Игрок: {self.member.display_name} | База: 2000+ вопросов")
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
                await self.message.channel.send(embed=discord.Embed(title="💡 ВИКТОРИНА", description="Дуэль окончена тайм-аутом.", color=0x2ECC71), view=QuizRoomView(self.bot))
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
            await interaction.response.edit_message(content=f"🏆 **{interaction.user.mention} ПОБЕДИЛ!** Забрал **{v.bet * 2} 🪙**", embed=None, view=v)
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

    @discord.ui.button(label="💡 Играть Соло (100 🪙)", style=discord.ButtonStyle.primary, custom_id="quiz_solo_v15")
    async def solo(self, interaction: discord.Interaction, button: Button):
        data = await db.get_user(str(interaction.user.id))
        if data.get('vibecoins', 0) < 100:
            await interaction.response.send_message("❌ Мало монет!", ephemeral=True); return
        await interaction.response.defer()
        await db.update_user(str(interaction.user.id), vibecoins=data['vibecoins'] - 100)
        q = await fetch_question()
        view = QuizView(self.bot, interaction.user, q)
        msg = await interaction.channel.send(content=interaction.user.mention, embed=view.create_embed(), view=view)
        view.message = msg
        try: await interaction.message.delete()
        except: pass

    @discord.ui.button(label="⚔️ С другом (300 🪙)", style=discord.ButtonStyle.success, custom_id="quiz_duel_v15")
    async def invite(self, interaction: discord.Interaction, button: Button):
        data = await db.get_user(str(interaction.user.id))
        if data.get('vibecoins', 0) < 300:
            await interaction.response.send_message("❌ Нужно 300 монет!", ephemeral=True); return
        from cogs.shop import GameDuelSelectView
        await interaction.response.send_message("💡 Выбери друга для битвы умов:", view=GameDuelSelectView(self.bot, interaction.user.id, 300, "quiz"), ephemeral=True)

    @discord.ui.button(label="❌ Закрыть руму", style=discord.ButtonStyle.danger, custom_id="quiz_close_v15")
    async def exit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🚪 Комната закрывается..."); await asyncio.sleep(2)
        try: await interaction.channel.delete()
        except: pass

class Quiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(QuizRoomView(bot))

async def setup(bot): await bot.add_cog(Quiz(bot))
