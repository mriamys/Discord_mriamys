import discord
from discord.ext import commands
import time
import math
import random
from utils.db import db
from datetime import datetime, timedelta
import logging
from config import PREFIX

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_sessions = {}  # {user_id: join_timestamp}
        self.msg_cooldowns = {}   # {user_id: last_msg_timestamp}

    @commands.Cog.listener()
    async def on_ready(self):
        # При запуске или рестарте бота проверяем, кто уже сидит в войсе с соблюдением правил (анти-абуз)
        now = time.time()
        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                non_bots = [m for m in vc.members if not m.bot]
                for member in vc.members:
                    if member.bot:
                        continue
                        
                    eligible = True
                    if guild.afk_channel and vc.id == guild.afk_channel.id:
                        eligible = False
                    elif getattr(member.voice, 'self_deaf', False) or getattr(member.voice, 'deaf', False):
                        eligible = False
                    elif len(non_bots) < 2:
                        eligible = False
                        
                    if eligible and str(member.id) not in self.voice_sessions:
                        self.voice_sessions[str(member.id)] = now

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
            
        # Игнорируем сообщения, которые начинаются как команды бота
        if message.content.startswith(PREFIX):
            return
            
        now = time.time()
        user_id = str(message.author.id)
        
        # Кулдаун 15 секунд на получение бонусов за текст
        last_msg = self.msg_cooldowns.get(user_id, 0)
        if now - last_msg < 15:
            return
            
        self.msg_cooldowns[user_id] = now
            
        # Начисляем VibeКоины и опыт за сообщения (рандом для интереса)
        user_data = await db.get_user(user_id)
        
        # 1-3 монетки за сообщение
        new_coins = user_data.get('vibecoins', 0) + random.randint(1, 3)
        # 15-25 XP за сообщение
        new_xp = user_data.get('xp', 0) + random.randint(15, 25)
        # Статы для ачивок
        new_msg_count = user_data.get('msg_count', 0) + 1
        
        await db.update_user(user_id, vibecoins=new_coins, xp=new_xp, msg_count=new_msg_count)
        
        # Вызываем диспетчер проверки уровня (это будет ловить Cog Leveling)
        self.bot.dispatch("xp_updated", message.author, new_xp)
        self.bot.dispatch("message_sent", message.author, new_msg_count)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Чтобы проверять одиночество в канале (анти-абуз),
        # мы должны перепроверять всех участников в каналах "до" и "после" изменения.
        users_to_check = {member}
        if before.channel:
            users_to_check.update(before.channel.members)
        if after.channel:
            users_to_check.update(after.channel.members)
            
        now = time.time()
        
        for u in users_to_check:
            if u.bot:
                continue
                
            eligible = False
            if u.voice and u.voice.channel:
                if u.guild.afk_channel and u.voice.channel.id == u.guild.afk_channel.id:
                    eligible = False
                elif u.voice.self_deaf or u.voice.deaf:
                    eligible = False
                else:
                    non_bots = [m for m in u.voice.channel.members if not m.bot]
                    if len(non_bots) >= 2:
                        eligible = True
                        
            user_id = str(u.id)
            
            # Начинаем трекать, если стал eligible
            if eligible and user_id not in self.voice_sessions:
                self.voice_sessions[user_id] = now
                
            # Заканчиваем трекать, если перестал быть eligible (вышел, замутился, остался один в канале)
            elif not eligible and user_id in self.voice_sessions:
                join_time = self.voice_sessions.pop(user_id)
                duration = int(now - join_time)
                
                if duration > 0:
                    user_data = await db.get_user(user_id)
                    old_seconds = user_data.get('voice_time_seconds', 0)
                    total_voice_time = old_seconds + duration
                    
                    # Считаем разницу, чтобы не терялись остатки секунд при переподключениях
                    old_minutes = old_seconds // 60
                    new_minutes = total_voice_time // 60
                    delta_minutes = new_minutes - old_minutes
                    
                    new_coins = user_data.get('vibecoins', 0) + (delta_minutes * 2)
                    new_xp = user_data.get('xp', 0) + (delta_minutes * 10)
                    
                    await db.update_user(user_id, 
                                         vibecoins=new_coins, 
                                         xp=new_xp, 
                                         voice_time_seconds=total_voice_time)
                    
                    if delta_minutes > 0:
                        self.bot.dispatch("xp_updated", u, new_xp)
                    self.bot.dispatch("voice_time_updated", u, total_voice_time)

async def setup(bot):
    await bot.add_cog(Economy(bot))
