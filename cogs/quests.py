import discord
from discord.ext import commands
import random
import logging
from utils.db import db
from datetime import datetime
from zoneinfo import ZoneInfo

# Набор шаблонов для ежедневных заданий
TASK_TEMPLATES = {
    "msg_30": {"name": "Болтун", "desc": "Отправить 30 сообщений в чаты сервера.", "target": 30, "type": "messages"},
    "msg_50": {"name": "Активный оратор", "desc": "Отправить 50 сообщений в чаты сервера.", "target": 50, "type": "messages"},
    "voice_60": {"name": "Голос Разума", "desc": "Провести 60 минут в голосовых каналах.", "target": 60, "type": "voice"},
    "voice_120": {"name": "Собеседник", "desc": "Провести 120 минут в голосовых каналах.", "target": 120, "type": "voice"},
    "casino_5": {"name": "Азартный малый", "desc": "Сыграть 5 раз в любое казино.", "target": 5, "type": "casino"},
    "casino_10": {"name": "Лудоман", "desc": "Сыграть 10 раз в любое казино.", "target": 10, "type": "casino"},
    "duel_2": {"name": "Удачливый боец", "desc": "Одержать победу в 2 дуэлях.", "target": 2, "type": "duels"},
    "duel_3": {"name": "Мастер меча", "desc": "Одержать победу в 3 дуэлях.", "target": 3, "type": "duels"},
    "case_2": {"name": "Любитель коробок", "desc": "Открыть 2 любых Vibe-кейса.", "target": 2, "type": "cases"},
    "reply_5": {"name": "Альфа-ответчик", "desc": "Ответить (через Reply) на сообщения 5 участников.", "target": 5, "type": "replies"},
    "bj_3": {"name": "Карточный долг", "desc": "Выиграть 3 партии в Блэкджек.", "target": 3, "type": "bj_wins"},
    "bj_5": {"name": "Король стола", "desc": "Выиграть 5 партий в Блэкджек.", "target": 5, "type": "bj_wins"},
    "quiz_3": {"name": "Всезнайка", "desc": "Верно ответить на 3 вопроса викторины.", "target": 3, "type": "quiz_correct"},
    "quiz_5": {"name": "Профессор", "desc": "Верно ответить на 5 вопросов викторины.", "target": 5, "type": "quiz_correct"},
    "shop_1": {"name": "Шопоголик", "desc": "Купить 1 любой товар в магазине.", "target": 1, "type": "shop_buy"},
    "nick_1": {"name": "Смена личности", "desc": "Сменить ник через магазин 1 раз.", "target": 1, "type": "nick_change"}
}

class DailyTasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def assign_new_task(self, member: discord.Member):
        """Выдает одно новое задание на день."""
        kyiv_tz = ZoneInfo("Europe/Kyiv")
        today = datetime.now(kyiv_tz).date()
        
        user_data = await db.get_user(str(member.id))
        last_task_date = user_data.get('quest_date') # Используем ту же колонку в БД
        
        if last_task_date == today:
            return None
            
        # Рандомный выбор задания
        tid = random.choice(list(TASK_TEMPLATES.keys()))
        task = TASK_TEMPLATES[tid]
        
        reward_coins = random.randint(600, 1800)
        reward_xp = random.randint(300, 1000)
        
        await db.update_user(str(member.id),
                             quest_id=tid,
                             quest_progress=0,
                             quest_target=task['target'],
                             quest_reward_coins=reward_coins,
                             quest_reward_xp=reward_xp,
                             quest_date=today)
        
        return {
            "name": task['name'],
            "desc": task['desc'],
            "reward_coins": reward_coins,
            "reward_xp": reward_xp
        }

    async def check_progress(self, member: discord.Member, qtype: str, increment: int = 1):
        user_data = await db.get_user(str(member.id))
        tid = user_data.get('quest_id')
        
        if not tid or tid not in TASK_TEMPLATES:
            return
            
        task = TASK_TEMPLATES[tid]
        if task['type'] != qtype:
            return
            
        new_progress = user_data.get('quest_progress', 0) + increment
        target = user_data.get('quest_target', 0)
        
        if new_progress >= target:
            await self._complete_task(member, user_data)
        else:
            await db.update_user(str(member.id), quest_progress=new_progress)

    async def _complete_task(self, member: discord.Member, user_data: dict):
        coins = user_data.get('quest_reward_coins', 0)
        xp = user_data.get('quest_reward_xp', 0)
        tid = user_data.get('quest_id')
        task_name = TASK_TEMPLATES[tid]['name']
        
        new_count = user_data.get('quests_completed', 0) + 1
        
        await db.update_user(str(member.id),
                             quest_id=None,
                             vibecoins=user_data.get('vibecoins', 0) + coins,
                             xp=user_data.get('xp', 0) + xp,
                             quests_completed=new_count)
        
        embed = discord.Embed(
            title="🌟 ЗАДАНИЕ ВЫПОЛНЕНО!",
            description=f"Поздравляем, ты завершил ежедневное задание **{task_name}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Награда", value=f"**{coins} 🪙**", inline=True)
        embed.add_field(name="⭐ Опыт", value=f"**{xp} XP**", inline=True)
        
        try:
            await member.send(embed=embed)
        except:
            pass
            
        self.bot.dispatch("xp_updated", member, user_data.get('xp', 0) + xp)
        self.bot.dispatch("balance_updated", member, user_data.get('vibecoins', 0) + coins)
        self.bot.dispatch("quest_completed", member, new_count)

    @commands.Cog.listener()
    async def on_blackjack_win(self, member, bj_wins):
        await self.check_progress(member, "bj_wins")

    @commands.Cog.listener()
    async def on_quiz_answered(self, member, correct, correct_count):
        if correct:
            await self.check_progress(member, "quiz_correct")

    @commands.Cog.listener()
    async def on_shop_purchased(self, member, item_id, shop_spent, nick_changes):
        await self.check_progress(member, "shop_buy")
        if item_id in ("nickname", "fake_status"):
            await self.check_progress(member, "nick_change")

    @commands.Cog.listener()
    async def on_message_sent(self, member, msg_count):
        await self.check_progress(member, "messages")

    @commands.Cog.listener()
    async def on_voice_time_updated(self, member, total_voice_time, delta_minutes=0):
        if delta_minutes > 0:
            await self.check_progress(member, "voice", delta_minutes)

    @commands.Cog.listener()
    async def on_casino_played(self, member, total_spent, total_wins, payout, bet):
        await self.check_progress(member, "casino")

    @commands.Cog.listener()
    async def on_duel_won(self, member, *args):
        await self.check_progress(member, "duels")

    @commands.Cog.listener()
    async def on_case_opened(self, member, *args):
        await self.check_progress(member, "cases")

    @commands.Cog.listener()
    async def on_message_reply_interaction(self, member, replied_to):
        await self.check_progress(member, "replies")

async def setup(bot):
    await bot.add_cog(DailyTasks(bot))
