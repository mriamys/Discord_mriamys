import discord
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
import aiohttp
import html
import time
from utils.db import db
from deep_translator import GoogleTranslator
from config import COLOR_MAIN, COLOR_SUCCESS, COLOR_ERROR

translator = GoogleTranslator(source='en', target='ru')

# Источник вопросов: Open Trivia DB (API)
OTDB_URL = "https://opentdb.com/api.php?amount=10&type=multiple"

_questions_cache = []

async def fetch_question():
    global _questions_cache
    if not _questions_cache:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(OTDB_URL, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('results'):
                            _questions_cache = data['results']
            except Exception as e:
                print(f"[Quiz] Error fetching from OTDB: {e}")
    
    if not _questions_cache:
        return {
            "q": "Какая планета самая большая в Солнечной системе?",
            "a": "Юпитер",
            "o": ["Марс", "Сатурн", "Нептун", "Юпитер"]
        }
    
    raw_q = _questions_cache.pop(0)
    try:
        q_text = html.unescape(raw_q['question'])
        correct_a = html.unescape(raw_q['correct_answer'])
        incorrect_as = [html.unescape(a) for a in raw_q['incorrect_answers']]
        to_translate = [q_text, correct_a] + incorrect_as
        # Перевод может быть медленным и блокирующим, пускаем в потоке
        translated = await asyncio.to_thread(translator.translate_batch, to_translate)
        q_translated = translated[0]
        a_translated = translated[1]
        opts_translated = translated[1:] 
        random.shuffle(opts_translated)
        return {"q": q_translated, "a": a_translated, "o": opts_translated}
    except Exception as e:
        print(f"[Quiz] Translation error: {e}")
        opts = [html.unescape(raw_q['correct_answer'])] + [html.unescape(a) for a in raw_q['incorrect_answers']]
        random.shuffle(opts)
        return {"q": html.unescape(raw_q['question']), "a": html.unescape(raw_q['correct_answer']), "o": opts}

class QuizView(View):
    def __init__(self, bot, member, q_data, bet=100):
        super().__init__(timeout=20.0)
        self.bot, self.member, self.q, self.bet = bot, member, q_data, bet
        self.message, self.ended = None, False
        self.end_timestamp = int(time.time() + 20)
        for opt in self.q['o']:
            self.add_item(QuizBtn(label=opt[:80], correct=opt == self.q['a']))
        exit_btn = Button(label="Закончить игру", style=discord.ButtonStyle.danger, row=2)
        exit_btn.callback = self._exit_callback
        self.add_item(exit_btn)

    async def create_embed(self, status=None, color=COLOR_MAIN):
        embed = discord.Embed(title="🌐 ВИКТОРИНА", description=f"**{self.q['q']}**", color=color)
        if status: embed.add_field(name="Результат", value=status, inline=False)
        else: embed.add_field(name="⏰ Время на ответ", value=f"<t:{self.end_timestamp}:R>", inline=True)
        embed.set_footer(text=f"Игрок: {self.member.display_name} | Ставка: {self.bet} 🪙")
        return embed

    async def on_timeout(self):
        if self.ended: return
        self.ended = True
        for c in self.children: c.disabled = True
        try:
            if self.message:
                await self.message.edit(content=f"⏰ **ВРЕМЯ ВЫШЛО!**\nПравильный ответ: `{self.q['a']}`", embed=None, view=self)
                await asyncio.sleep(4)
                await self._next_round()
        except: pass

    async def _next_round(self):
        if self.ended and self.message is None: return 
        new_q = await fetch_question()
        new_v = QuizView(self.bot, self.member, new_q, self.bet)
        new_msg = await self.message.channel.send(content=f"{self.member.mention} 💡 **Следующий вопрос!** (Ставка: {self.bet} 🪙)", embed=await new_v.create_embed(), view=new_v)
        new_v.message = new_msg

    async def _exit_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id: return
        self.ended = True
        self.stop()
        await interaction.response.send_message("👋 Викторина окончена!", ephemeral=True)
        try: await interaction.message.delete()
        except: pass
        await self._return_to_menu()

    async def _return_to_menu(self):
        desc = "**Выбирай режим:**\n🔹 Соло: На коины (множитель до 2.5x)\n🔹 Дуэль: Победитель забирает ставку проигравшего!"
        await self.message.channel.send(embed=discord.Embed(title="💡 ВИКТОРИНА", description=desc, color=0x2ECC71), view=QuizRoomView(self.bot))

class QuizBtn(Button):
    def __init__(self, label, correct):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.correct = correct

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if interaction.user.id != v.member.id or v.ended: return
        v.ended, v.stop() = True, True
        for c in v.children: 
            if isinstance(c, Button) and c.label != "Закончить игру":
                c.disabled = True
                if hasattr(c, 'correct') and c.correct: c.style = discord.ButtonStyle.success
                elif c.label == self.label: c.style = discord.ButtonStyle.danger
        
        data = await db.get_user(str(v.member.id))
        if self.correct:
            reward = int(v.bet * random.uniform(1.1, 2.5))
            await db.update_user(str(v.member.id), vibecoins=data['vibecoins'] + reward, quiz_correct=data.get('quiz_correct', 0) + 1)
            await interaction.response.edit_message(content=f"✅ **ВЕРНО!** Ты заработал **{reward} 🪙**", embed=await v.create_embed(status=f"Правильно: `{v.q['a']}`\nПриз: **+{reward} 🪙**", color=COLOR_SUCCESS), view=v)
        else:
            penalty = v.bet
            await db.update_user(str(v.member.id), vibecoins=max(0, data['vibecoins'] - penalty))
            await interaction.response.edit_message(content=f"❌ **ОШИБКА!**", embed=await v.create_embed(status=f"Твой ответ: `{self.label}`\nПравильный: `{v.q['a']}`\nШтраф: **-{penalty} 🪙**", color=COLOR_ERROR), view=v)
        await asyncio.sleep(4)
        await v._next_round()

class QuizDuelView(View):
    def __init__(self, bot, p1, p2, bet, q):
        super().__init__(timeout=25.0)
        self.bot, self.p1, self.p2, self.p_ids, self.bet, self.q = bot, p1, p2, [p1.id, p2.id], bet, q
        self.message, self.ended, self.players_wrong = None, False, set()
        self.end_timestamp = int(time.time() + 25)
        for opt in self.q['o']: self.add_item(QuizDuelBtn(label=opt[:80], correct=opt == q['a']))
        exit_btn = Button(label="Закончить дуэль", style=discord.ButtonStyle.danger, row=2)
        exit_btn.callback = self._exit_callback
        self.add_item(exit_btn)

    async def create_embed(self, winner=None, loser=None, all_failed=False):
        color = COLOR_MAIN
        if winner: color = COLOR_SUCCESS
        elif all_failed: color = COLOR_ERROR
        embed = discord.Embed(title="⚔️ ДУЭЛЬ ЗНАТОКОВ", description=f"**{self.q['q']}**", color=color)
        embed.add_field(name="💰 Ставка", value=f"**{self.bet} 🪙**", inline=True)
        if winner:
            embed.add_field(name="🏆 Победитель", value=f"<@{winner}> (+{self.bet} 🪙)", inline=False)
            embed.add_field(name="💀 Проигравший", value=f"<@{loser}> (-{self.bet} 🪙)", inline=False)
            embed.add_field(name="✅ Ответ", value=f"`{self.q['a']}`", inline=True)
        elif all_failed:
            embed.add_field(name="💀 Финал", value=f"Никто не ответил! Оба потеряли по {self.bet} 🪙", inline=False)
            embed.add_field(name="✅ Ответ был", value=f"`{self.q['a']}`", inline=True)
        else:
            embed.add_field(name="⏰ Время", value=f"<t:{self.end_timestamp}:R>", inline=True)
            embed.add_field(name="❌ Ошиблись", value=", ".join([f"<@{pid}>" for pid in self.players_wrong]) or "Нет", inline=False)
        return embed

    async def on_timeout(self):
        if self.ended: return
        self.ended = True
        for c in self.children: c.disabled = True
        if self.message:
            # Если время вышло, оба теряют ставочку (или штраф)
            penalty = self.bet
            for pid in self.p_ids:
                u = await db.get_user(str(pid))
                await db.update_user(str(pid), vibecoins=max(0, u['vibecoins'] - penalty))
            await self.message.edit(content="⏰ **ВРЕМЯ ВЫШЛО! Оба оштрафованы!**", embed=await self.create_embed(all_failed=True), view=self)
            await asyncio.sleep(5)
            await self._next_round()

    async def _next_round(self):
        if self.ended and self.message is None: return
        new_q = await fetch_question()
        new_v = QuizDuelView(self.bot, self.p1, self.p2, self.bet, new_q)
        new_msg = await self.message.channel.send(content=f"⚔️ {self.p1.mention} 🆚 {self.p2.mention}\n💡 **Новый раунд!** Ставка: {self.bet} 🪙", embed=await new_v.create_embed(), view=new_v)
        new_v.message = new_msg

    async def _exit_callback(self, interaction: discord.Interaction):
        if interaction.user.id not in self.p_ids: return
        self.ended = True
        self.stop()
        await interaction.response.send_message(f"👋 {interaction.user.display_name} закончил дуэль!", ephemeral=True)
        try: await interaction.message.delete()
        except: pass
        await self._return_to_menu()

    async def _return_to_menu(self):
        desc = "**Выбирай режим:**\n🔹 Соло: Ошибка = -Ставка 🪙\n🔹 Дуэль: Ошибка = -Ставка 🪙"
        await self.message.channel.send(embed=discord.Embed(title="💡 ВИКТОРИНА", description=desc, color=0x2ECC71), view=QuizRoomView(self.bot))

class QuizDuelBtn(Button):
    def __init__(self, label, correct):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.correct = correct

    async def callback(self, interaction: discord.Interaction):
        v = self.view
        if interaction.user.id not in v.p_ids or v.ended: return
        if interaction.user.id in v.players_wrong:
            await interaction.response.send_message("❌ Ты уже ошибся!", ephemeral=True); return
        if self.correct:
            v.ended, v.stop() = True, True
            loser_id = v.p1.id if interaction.user.id == v.p2.id else v.p2.id
            w_data = await db.get_user(str(interaction.user.id))
            l_data = await db.get_user(str(loser_id))
            await db.update_user(str(interaction.user.id), vibecoins=w_data['vibecoins'] + v.bet, quiz_correct=w_data.get('quiz_correct', 0) + 1)
            await db.update_user(str(loser_id), vibecoins=max(0, l_data['vibecoins'] - v.bet))
            for c in v.children:
                c.disabled = True
                if isinstance(c, Button) and c.label != "Закончить дуэль":
                    if hasattr(c, 'correct') and c.correct: c.style = discord.ButtonStyle.success
                    elif c.label == self.label: c.style = discord.ButtonStyle.danger
            await interaction.response.edit_message(content=f"🏆 **{interaction.user.mention} КРАСАВА!**", embed=await v.create_embed(winner=interaction.user.id, loser=loser_id), view=v)
            await asyncio.sleep(5)
            await v._next_round()
        else:
            v.players_wrong.add(interaction.user.id)
            self.style, self.disabled = discord.ButtonStyle.danger, True
            if len(v.players_wrong) >= len(v.p_ids):
                v.ended, v.stop() = True, True
                for pid in v.p_ids:
                    u = await db.get_user(str(pid))
                    await db.update_user(str(pid), vibecoins=max(0, u['vibecoins'] - v.bet))
                for c in v.children: 
                    c.disabled = True
                    if isinstance(c, Button) and c.label != "Закончить дуэль" and hasattr(c, 'correct') and c.correct: c.style = discord.ButtonStyle.success
                await interaction.response.edit_message(content="💀 **ОБА ОШИБЛИСЬ! Минус коины.**", embed=await v.create_embed(all_failed=True), view=v)
                await asyncio.sleep(5)
                await v._next_round()
            else:
                await interaction.response.edit_message(embed=await v.create_embed(), view=v)
                await interaction.followup.send("❌ Неправильно! Ты теряешь шанс в этом раунде.", ephemeral=True)

class QuizBetModal(discord.ui.Modal):
    def __init__(self, bot, mode="duel"):
        super().__init__(title="💡 Викторина: Введите ставку")
        self.bot, self.mode = bot, mode
        self.bet_input = discord.ui.TextInput(label="Ставка", placeholder="Например: 500", min_length=1, max_length=10)
        self.add_item(self.bet_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            bet = int(self.bet_input.value)
            if bet < 10: raise ValueError
        except:
            await interaction.followup.send("❌ Введите корректное число!", ephemeral=True); return
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < bet:
            await interaction.followup.send("❌ Мало коинов!", ephemeral=True); return
        if self.mode == "solo":
            q = await fetch_question()
            view = QuizView(self.bot, interaction.user, q, bet)
            msg = await interaction.channel.send(content=f"{interaction.user.mention} 💡 **Викторина началась!**", embed=await view.create_embed(), view=view)
            view.message = msg
        else:
            from cogs.shop import GameDuelSelectView
            await interaction.followup.send(f"💡 Готовим дуэль! Ставка: **{bet} 🪙**", view=GameDuelSelectView(self.bot, interaction.user.id, bet, "quiz"), ephemeral=True)

class QuizBetView(View):
    def __init__(self, bot, mode="duel"):
        super().__init__(timeout=60)
        self.bot, self.mode = bot, mode
    @discord.ui.button(label="100", style=discord.ButtonStyle.secondary)
    async def bet_100(self, interaction, button): await self.start(interaction, 100)
    @discord.ui.button(label="300", style=discord.ButtonStyle.secondary)
    async def bet_300(self, interaction, button): await self.start(interaction, 300)
    @discord.ui.button(label="1000", style=discord.ButtonStyle.secondary)
    async def bet_1k(self, interaction, button): await self.start(interaction, 1000)
    @discord.ui.button(label="Своя ставка", style=discord.ButtonStyle.primary)
    async def bet_custom(self, interaction, button): await interaction.response.send_modal(QuizBetModal(self.bot, self.mode))

    async def start(self, interaction, bet):
        await interaction.response.defer(ephemeral=True)
        user_data = await db.get_user(str(interaction.user.id))
        if user_data.get('vibecoins', 0) < bet:
            await interaction.followup.send("❌ Недостаточно коинов!", ephemeral=True); return
        if self.mode == "solo":
            q = await fetch_question()
            view = QuizView(self.bot, interaction.user, q, bet)
            msg = await interaction.channel.send(content=f"{interaction.user.mention} 💡 **Викторина началась!**", embed=await view.create_embed(), view=view)
            view.message = msg
        else:
            from cogs.shop import GameDuelSelectView
            await interaction.followup.send(f"💡 Готовим дуэль! Ставка: **{bet} 🪙**", view=GameDuelSelectView(self.bot, interaction.user.id, bet, "quiz"), ephemeral=True)

class QuizRoomView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot, self._busy = bot, False
    @discord.ui.button(label="💡 Играть Соло (На коины)", style=discord.ButtonStyle.primary, custom_id="quiz_solo_btn")
    async def solo(self, interaction: discord.Interaction, button: Button):
        if self._busy: return
        self._busy = True
        try: await interaction.message.delete()
        except: pass
        await interaction.response.send_message("💰 Выберите ставку на каждый вопрос:", view=QuizBetView(self.bot, mode="solo"), ephemeral=True)
    @discord.ui.button(label="⚔️ Дуэль (На коины)", style=discord.ButtonStyle.success, custom_id="quiz_duel_btn")
    async def invite(self, interaction: discord.Interaction, button: Button):
        if self._busy: return
        await interaction.response.send_message("💰 Выберите ставку за неверный ответ:", view=QuizBetView(self.bot, mode="duel"), ephemeral=True)
    @discord.ui.button(label="❌ Закрыть руму", style=discord.ButtonStyle.danger, custom_id="quiz_close_btn")
    async def exit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🚪 Комната закрывается..."); await asyncio.sleep(1); try: await interaction.channel.delete()
        except: pass

class Quiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("[Quiz] Cog initialized")

async def setup(bot):
    try:
        cog = Quiz(bot)
        await bot.add_cog(cog)
        # Регистрируем View для обработки кнопок даже после рестарта
        bot.add_view(QuizRoomView(bot))
        print("[Quiz] Cog and View loaded successfully")
    except Exception as e:
        print(f"[Quiz] Critical error in setup: {e}")
        import logging
        logging.error(f"Failed to setup Quiz cog: {e}")
