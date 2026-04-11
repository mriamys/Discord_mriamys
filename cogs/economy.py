import discord
from discord.ext import commands
import time
import math
from utils.db import db
from datetime import datetime, timedelta
import logging

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_sessions = {}  # {user_id: join_timestamp}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
            
        # Начисляем немного VibeКоинов и опыта за сообщения
        user_data = await db.get_user(str(message.author.id))
        
        # 1-3 монетки за сообщение
        new_coins = user_data.get('vibecoins', 0) + 2
        # 5-10 XP за сообщение
        new_xp = user_data.get('xp', 0) + 5
        # Статы для ачивок
        new_msg_count = user_data.get('msg_count', 0) + 1
        
        await db.update_user(str(message.author.id), vibecoins=new_coins, xp=new_xp, msg_count=new_msg_count)
        
        # Вызываем диспетчер проверки уровня (это будет ловить Cog Leveling)
        self.bot.dispatch("xp_updated", message.author, new_xp)
        self.bot.dispatch("message_sent", message.author, new_msg_count)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
            
        user_id = str(member.id)
        
        # Зашел в канал
        if before.channel is None and after.channel is not None:
            self.voice_sessions[user_id] = time.time()
            
        # Вышел из канала
        elif before.channel is not None and after.channel is None:
            if user_id in self.voice_sessions:
                join_time = self.voice_sessions.pop(user_id)
                duration = int(time.time() - join_time)
                
                # За каждую минуту (60 сек) даем 10 VibeКоинов и 20 XP
                minutes = duration // 60
                if minutes > 0:
                    user_data = await db.get_user(user_id)
                    new_coins = user_data.get('vibecoins', 0) + (minutes * 10)
                    new_xp = user_data.get('xp', 0) + (minutes * 20)
                    total_voice_time = user_data.get('voice_time_seconds', 0) + duration
                    
                    await db.update_user(user_id, 
                                         vibecoins=new_coins, 
                                         xp=new_xp, 
                                         voice_time_seconds=total_voice_time)
                    
                    self.bot.dispatch("xp_updated", member, new_xp)
                    self.bot.dispatch("voice_time_updated", member, total_voice_time)

async def setup(bot):
    await bot.add_cog(Economy(bot))
