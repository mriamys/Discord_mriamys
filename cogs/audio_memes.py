import discord
from discord.ext import commands, tasks
from utils.db import db
import asyncio
import random
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AudioMemes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_trolls = {} # { user_id: { 'channel_id': int, 'count': 0, 'end_time': datetime, 'guild_id': int } }
        self.troll_loop.start()

    def cog_unload(self):
        self.troll_loop.cancel()

    @commands.Cog.listener()
    async def on_voice_meme_purchased(self, user: discord.Member, channel: discord.VoiceChannel):
        """Событие покупки аудио-троллинга."""
        self.active_trolls[user.id] = {
            'channel_id': channel.id,
            'count': 0,
            'end_time': datetime.utcnow().timestamp() + 3600, # 1 час
            'guild_id': user.guild.id
        }
        
        # Обновляем статистику для ачивок
        user_data = await db.get_user(str(user.id))
        memes_ordered = user_data.get('memes_ordered', 0) + 1
        await db.update_user(str(user.id), memes_ordered=memes_ordered)
        
        # Проверяем и выдаем ачивку
        user.client.dispatch("meme_ordered", user, memes_ordered)

    @tasks.loop(minutes=2)
    async def troll_loop(self):
        """Цикл проверки активных заказов на троллинг."""
        now = datetime.utcnow().timestamp()
        to_remove = []

        for user_id, data in list(self.active_trolls.items()):
            if data['count'] >= 10 or now > data['end_time']:
                to_remove.append(user_id)
                continue

            # Шанс 40% каждые 2 минуты зайти и проиграть мем
            if random.random() < 0.4:
                guild = self.bot.get_guild(data['guild_id'])
                if not guild: continue
                member = guild.get_member(user_id)
                if not member or not member.voice or not member.voice.channel:
                    continue # Ждем, пока пользователь снова зайдет в войс
                
                channel = member.voice.channel
                # Пробуем зайти и сыграть (используем отдельный таск, чтобы не блокировать цикл)
                self.bot.loop.create_task(self.play_meme(channel, guild))
                self.active_trolls[user_id]['count'] += 1

        for uid in to_remove:
            del self.active_trolls[uid]

    @troll_loop.before_loop
    async def before_troll_loop(self):
        await self.bot.wait_until_ready()

    async def get_random_meme_url(self):
        """Парсим рандомный мем с myinstants"""
        import aiohttp
        import re
        url = "https://www.myinstants.com/ru/search/?name=%D0%BC%D0%B5%D0%BC%D1%8B"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        # Парсим пути к mp3 файлам (используем set для удаления дубликатов)
                        matches = list(set(re.findall(r"/media/sounds/[^\".']+\.mp3", html)))
                        if matches:
                            return "https://www.myinstants.com" + random.choice(matches)
        except Exception as e:
            logger.error(f"Ошибка при парсинге мемов: {e}")
        return None

    async def play_meme(self, channel: discord.VoiceChannel, guild: discord.Guild):
        """Проигрывание случайного мема в голосовом канале."""
        meme_source = None
        
        # Пробуем сначала спарсить из веб
        meme_url = await self.get_random_meme_url()
        if meme_url:
            meme_source = meme_url
        else:
            # Фолбэк на локальные файлы, если сайт отвалился
            audio_dir = "audio/memes"
            if os.path.exists(audio_dir):
                files = [f for f in os.listdir(audio_dir) if f.endswith(('.mp3', '.wav', '.ogg'))]
                if files:
                    meme_source = os.path.join(audio_dir, random.choice(files))
                    
        if not meme_source:
            return

        # Пытаемся подключиться
        voice_client = discord.utils.get(self.bot.voice_clients, guild=guild)
        
        try:
            if not voice_client:
                voice_client = await channel.connect()
            elif voice_client.channel != channel:
                await voice_client.move_to(channel)
        except Exception as e:
            logger.error(f"Не удалось подключиться к каналу для мема: {e}")
            return

        if voice_client.is_playing():
            return # Уже что-то играет
            
        try:
            # Ограничиваем время воспроизведения до 10 секунд (через параметры FFmpeg)
            audio_source = discord.FFmpegPCMAudio(
                source=meme_source,
                options="-t 10"  # Форсированно обрываем через 10 секунд, если мем слишком длинный
            )
            voice_client.play(audio_source)
            
            # Ждем пока доиграет
            while voice_client.is_playing():
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Ошибка воспроизведения мема: {e}")
            
        # Отключаемся с небольшой задержкой
        await asyncio.sleep(1)
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()


async def setup(bot):
    await bot.add_cog(AudioMemes(bot))
