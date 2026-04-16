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
        self.active_trolls = {} # { user_id: { 'count': 0, 'end_time': timestamp } }
        self.troll_loop.start()

    def cog_unload(self):
        self.troll_loop.cancel()

    @commands.Cog.listener()
    async def on_voice_meme_purchased(self, user: discord.Member, channel: discord.VoiceChannel):
        """Событие покупки аудио-троллинга."""
        self.active_trolls[user.id] = {
            'count': 0,
            'end_time': datetime.utcnow().timestamp() + 3600 # 1 час
        }
        
        # Статистика для ачивок (общая)
        user_data = await db.get_user(str(user.id))
        memes_ordered = user_data.get('memes_ordered', 0) + 1
        await db.update_user(str(user.id), memes_ordered=memes_ordered)
        
        # Диспатчим ивент для ачивок
        self.bot.dispatch("meme_ordered", user, memes_ordered)

    @tasks.loop(minutes=2)
    async def troll_loop(self):
        """Цикл проверки активных заказов на троллинг."""
        now = datetime.utcnow().timestamp()
        
        # На первом запуске загружаем из БД
        if not hasattr(self, '_initial_loaded'):
            active_from_db = await db.get_active_voice_memes()
            for row in active_from_db:
                uid = int(row['user_id'])
                if uid not in self.active_trolls:
                    self.active_trolls[uid] = {
                        'count': row['voice_memes_count'],
                        'end_time': row['voice_memes_until'].timestamp()
                    }
            self._initial_loaded = True

        to_remove = []

        for user_id, data in list(self.active_trolls.items()):
            # Проверяем условия окончания
            reason = None
            if data['count'] >= 10:
                reason = "лимит проигрываний (10/10) исчерпан"
            elif now > data['end_time']:
                reason = "время действия (1 час) истекло"

            if reason:
                to_remove.append(user_id)
                # Уведомляем пользователя
                guild = self.bot.get_guild(next(iter(self.bot.guilds)).id) # Предполагаем основную гильдию
                if guild:
                    member = guild.get_member(user_id)
                    if member:
                        embed = discord.Embed(
                            title="🔊 Рандом высер окончен",
                            description=f"Твой аудио-троллинг завершен, так как {reason}.\nНадеемся, это было весело! 🤡",
                            color=0x2b2d31
                        )
                        chan = discord.utils.get(guild.text_channels, name="📜┃ранг")
                        try:
                            if chan:
                                await chan.send(content=member.mention, embed=embed)
                            else:
                                await member.send(embed=embed)
                        except: pass
                
                # Чистим в БД
                await db.update_user(str(user_id), voice_memes_until=None, voice_memes_count=0)
                continue

            # Шанс 40% каждые 2 минуты зайти и проиграть мем
            if random.random() < 0.4:
                # Находим участника в любой из гильдий бота
                member = None
                for g in self.bot.guilds:
                    member = g.get_member(user_id)
                    if member: break
                    
                if not member or not member.voice or not member.voice.channel:
                    continue 
                
                channel = member.voice.channel
                guild = member.guild
                
                # Пробуем зайти и сыграть
                self.bot.loop.create_task(self.play_meme(channel, guild))
                
                # Инкрементируем и сохраняем
                self.active_trolls[user_id]['count'] += 1
                await db.update_user(str(user_id), voice_memes_count=self.active_trolls[user_id]['count'])

        for uid in to_remove:
            if uid in self.active_trolls:
                del self.active_trolls[uid]

    @troll_loop.before_loop
    async def before_troll_loop(self):
        await self.bot.wait_until_ready()

    async def get_random_meme_url(self):
        """Парсим рандомный мем с myinstants"""
        import aiohttp
        import re
        import random
        page = random.randint(1, 10)
        url = f"https://www.myinstants.com/ru/search/?name=%D0%BC%D0%B5%D0%BC%D1%8B&page={page}"
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

    def is_channel_active(self, channel_id: int) -> bool:
        """Проверяет, активен ли троллинг в конкретном канале."""
        # Для этого нам нужно знать, в каких каналах сейчас сидят троллируемые
        for user_id in self.active_trolls:
            for guild in self.bot.guilds:
                m = guild.get_member(user_id)
                if m and m.voice and m.voice.channel and m.voice.channel.id == channel_id:
                    return True
        return False


async def setup(bot):
    await bot.add_cog(AudioMemes(bot))
