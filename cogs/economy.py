import discord
from discord.ext import commands, tasks
import time
import math
import random
from utils.db import db
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging
from config import PREFIX

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_sessions = {}  # {user_id: join_timestamp}
        self.msg_cooldowns = {}   # {user_id: last_msg_timestamp}
        self.save_voice_sessions.start()
        self.check_boost_expirations.start()

    def cog_unload(self):
        self.save_voice_sessions.cancel()
        self.check_boost_expirations.cancel()

    @tasks.loop(minutes=1)
    async def check_boost_expirations(self):
        expired = await db.get_expired_boosts()
        for row in expired:
            user_id = row['user_id']
            xp_gained = row.get('xp_boost_xp_gained', 0)
            coins_gained = row.get('xp_boost_coins_gained', 0)
            
            # Сбрасываем буст полностью
            await db.update_user(user_id, 
                                 xp_boost_until=None, 
                                 xp_boost_remaining=0,
                                 xp_boost_xp_gained=0,
                                 xp_boost_coins_gained=0)
            
            member = None
            guild = None
            for g in self.bot.guilds:
                member = g.get_member(int(user_id))
                if member:
                    guild = g
                    break
            
            if member and guild:
                embed = discord.Embed(
                    title="⚡ Буст опыта x2 завершен",
                    description=f"{member.mention}, время действия твоего буста истекло.",
                    color=0xFFD700
                )
                embed.add_field(name="📊 Отчет по бусту", value=(
                    f"▫️ Получено опыта: **+{int(xp_gained)} XP**\n"
                    f"▫️ Получено коинов: **+{int(coins_gained)} 🪙**"
                ))
                embed.set_footer(text="Буст работал только во время активного фарма опыта.")
                
                chan = discord.utils.get(guild.text_channels, name="📜┃ранг")
                try:
                    if chan: await chan.send(content=member.mention, embed=embed)
                    else: await member.send(embed=embed)
                except: pass

    @tasks.loop(minutes=2)
    async def save_voice_sessions(self):
        now = time.time()
        for user_id, join_time in list(self.voice_sessions.items()):
            duration = int(now - join_time)
            if duration >= 60:
                user = None
                for guild in self.bot.guilds:
                    user = guild.get_member(int(user_id))
                    if user: break
                if not user:
                    user = self.bot.get_user(int(user_id))
                
                await self._process_voice_duration(user, user_id, duration)
                if user_id in self.voice_sessions:
                    self.voice_sessions[user_id] = now

    def _is_eligible(self, member):
        if not member or member.bot: return False
        if not member.voice or not member.voice.channel: return False
        
        # AFK канал
        if member.guild.afk_channel and member.voice.channel.id == member.guild.afk_channel.id:
            return False
            
        # Мут ушей
        if member.voice.self_deaf or member.voice.deaf:
            return False
            
        # Один в канале
        non_bots = [m for m in member.voice.channel.members if not m.bot]
        if len(non_bots) < 2:
            return False
            
        return True

    @commands.Cog.listener()
    async def on_ready(self):
        now = time.time()
        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                for member in vc.members:
                    if self._is_eligible(member):
                        user_id = str(member.id)
                        if user_id not in self.voice_sessions:
                            self.voice_sessions[user_id] = now
                            # При запуске проверяем, нужно ли снять буст с паузы
                            await self._manage_boost_state(member, True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild or message.content.startswith(PREFIX):
            return
            
        now = time.time()
        user_id = str(message.author.id)
        
        last_msg = self.msg_cooldowns.get(user_id, 0)
        if now - last_msg < 15: return
        self.msg_cooldowns[user_id] = now
            
        user_data = await db.get_user(user_id)
        
        xp_multiplier = 1
        is_boosted = False
        xp_boost_until = user_data.get('xp_boost_until')
        
        if xp_boost_until:
            if isinstance(xp_boost_until, str):
                xp_boost_until = datetime.strptime(str(xp_boost_until).split('.')[0], '%Y-%m-%d %H:%M:%S')
            if xp_boost_until > datetime.utcnow():
                xp_multiplier = 2
                is_boosted = True
        
        coins_add = random.randint(1, 3)
        xp_base = random.randint(15, 25)
        xp_add = xp_base * xp_multiplier
        
        new_coins = user_data.get('vibecoins', 0) + coins_add
        new_xp = user_data.get('xp', 0) + xp_add
        
        # Обновляем статистику буста если активен
        boost_xp_stats = user_data.get('xp_boost_xp_gained', 0)
        boost_coins_stats = user_data.get('xp_boost_coins_gained', 0)
        if is_boosted:
            boost_xp_stats += (xp_add - xp_base) # Только бонусная часть
            boost_coins_stats += coins_add # Коины тоже считаем в отчет
            
        await db.update_user(user_id, 
                             vibecoins=new_coins, 
                             xp=new_xp, 
                             msg_count=user_data.get('msg_count', 0) + 1,
                             xp_boost_xp_gained=boost_xp_stats,
                             xp_boost_coins_gained=boost_coins_stats)
        
        self.bot.dispatch("xp_updated", message.author, new_xp)
        if message.reference and isinstance(message.reference.resolved, discord.Message):
            replied_to = message.reference.resolved.author
            if replied_to.id != message.author.id and not replied_to.bot:
                self.bot.dispatch("message_reply_interaction", message.author, replied_to)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        users_to_check = {member}
        if before.channel: users_to_check.update(before.channel.members)
        if after.channel: users_to_check.update(after.channel.members)
            
        now = time.time()
        for u in users_to_check:
            eligible = self._is_eligible(u)
            user_id = str(u.id)
            
            if eligible and user_id not in self.voice_sessions:
                self.voice_sessions[user_id] = now
                # Снимаем буст с паузы
                await self._manage_boost_state(u, True)
                self.bot.dispatch("voice_role_interaction", u, u.voice.channel.members)
            elif not eligible and user_id in self.voice_sessions:
                join_time = self.voice_sessions.pop(user_id)
                duration = int(now - join_time)
                await self._process_voice_duration(u, user_id, duration)
                # Ставим буст на паузу
                await self._manage_boost_state(u, False)

    async def _manage_boost_state(self, member, active: bool):
        user_id = str(member.id)
        user_data = await db.get_user(user_id)
        now = datetime.utcnow()
        
        if active:
            # Снимаем с паузы
            remaining = user_data.get('xp_boost_remaining', 0)
            if remaining > 0:
                new_until = now + timedelta(seconds=remaining)
                await db.update_user(user_id, xp_boost_until=new_until, xp_boost_remaining=0)
        else:
            # Ставим на паузу
            boost_until = user_data.get('xp_boost_until')
            if boost_until:
                if isinstance(boost_until, str):
                    boost_until = datetime.strptime(str(boost_until).split('.')[0], '%Y-%m-%d %H:%M:%S')
                
                if boost_until > now:
                    remaining = int((boost_until - now).total_seconds())
                    await db.update_user(user_id, xp_boost_until=None, xp_boost_remaining=remaining)
                else:
                    # Буст уже истек, пока он сидел
                    pass 

    async def _process_voice_duration(self, u, user_id, duration):
        if duration <= 0: return
        user_data = await db.get_user(user_id)
        
        old_seconds = user_data.get('voice_time_seconds', 0)
        total_voice_time = old_seconds + duration
        delta_minutes = (total_voice_time // 60) - (old_seconds // 60)
        
        # Стрик система (упрощенно как было)
        kyiv_tz = ZoneInfo("Europe/Kyiv")
        today = datetime.now(kyiv_tz).date()
        last_daily = user_data.get('last_daily')
        streak = user_data.get('streak', 0)
        last_daily_date = None
        if last_daily:
            if isinstance(last_daily, str): last_daily = datetime.strptime(str(last_daily).split('.')[0], '%Y-%m-%d %H:%M:%S')
            last_daily_date = last_daily.replace(tzinfo=ZoneInfo("UTC")).astimezone(kyiv_tz).date()
        
        streak_bonus = 0
        if last_daily_date != today:
            if last_daily_date == today - timedelta(days=1): streak += 1
            else: streak = 1
            last_daily = datetime.utcnow()
            streak_bonus = min(streak * 100, 3000)
            if u:
                try: await u.send(f"🔥 Твой войс-стрик обновлен! День: **{streak}**, Бонус: **{streak_bonus} 🪙**")
                except: pass
                self.bot.dispatch("streak_updated", u, streak)

        # Проверка буста
        xp_multiplier = 1
        is_boosted = False
        xp_boost_until = user_data.get('xp_boost_until')
        if xp_boost_until:
            if isinstance(xp_boost_until, str):
                xp_boost_until = datetime.strptime(str(xp_boost_until).split('.')[0], '%Y-%m-%d %H:%M:%S')
            if xp_boost_until > datetime.utcnow():
                xp_multiplier = 2
                is_boosted = True

        coins_add = (delta_minutes * 6) + streak_bonus
        xp_base = (delta_minutes * 10)
        xp_add = xp_base * xp_multiplier
        
        boost_xp_stats = user_data.get('xp_boost_xp_gained', 0)
        boost_coins_stats = user_data.get('xp_boost_coins_gained', 0)
        if is_boosted:
            boost_xp_stats += (xp_add - xp_base)
            boost_coins_stats += (delta_minutes * 6)

        await db.update_user(user_id,
                             vibecoins=user_data.get('vibecoins', 0) + coins_add,
                             xp=user_data.get('xp', 0) + xp_add,
                             voice_time_seconds=total_voice_time,
                             streak=streak,
                             last_daily=last_daily,
                             xp_boost_xp_gained=boost_xp_stats,
                             xp_boost_coins_gained=boost_coins_stats)

        if u and delta_minutes > 0:
            self.bot.dispatch("xp_updated", u, user_data.get('xp', 0) + xp_add)
            self.bot.dispatch("voice_time_updated", u, total_voice_time, delta_minutes)

    @discord.app_commands.command(name="give-money", description="[Admin] Выдать VibeКоины пользователю")
    @discord.app_commands.default_permissions(administrator=True)
    async def give_money(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if interaction.user.id != interaction.guild.owner_id:
            return await interaction.response.send_message("❌ Только для владельца.", ephemeral=True)
        user_data = await db.get_user(str(member.id))
        new_coins = user_data.get('vibecoins', 0) + amount
        await db.update_user(str(member.id), vibecoins=new_coins)
        await interaction.response.send_message(f"✅ Выдано **{amount} 🪙** {member.mention}. Итого: **{new_coins} 🪙**")

async def setup(bot):
    await bot.add_cog(Economy(bot))
