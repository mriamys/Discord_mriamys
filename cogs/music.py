import discord
from discord.ext import commands
import yt_dlp
import asyncio
import aiohttp
import re
import logging
from config import COLOR_SUCCESS, COLOR_ERROR

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -reconnect_on_network_error 1 -reconnect_on_http_error 4xx,5xx',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        duration = data.get('duration', 0)
        if duration and duration > 600:
            raise ValueError(f"Трек слишком длинный ({int(duration//60)} мин). Максимальная длина — 10 минут!")

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {} # guild_id -> list of urls

    async def check_channel(self, ctx):
        """Вспомогательная проверка канала."""
        channel_name = ctx.channel.name.lower()
        if "музыка" not in channel_name and "music" not in channel_name:
            music_channel = discord.utils.get(ctx.guild.text_channels, name="🎵┃музыка")
            if not music_channel:
                music_channel = discord.utils.get(ctx.guild.text_channels, name="музыка")
            
            hint = f" в канале {music_channel.mention}" if music_channel else ""
            await ctx.send(f"❌ Музыкальные команды можно использовать только{hint}!", ephemeral=True)
            return False
        return True

    async def get_spotify_track_info(self, url):
        # Ленивый парсинг Spotify без API (читаем Title страницы)
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    html = await response.text()
                    match = re.search(r'<title>(.+?)</title>', html)
                    if match:
                        full_title = match.group(1)
                        # Обычно формат "Track Title - song and lyrics by Artist | Spotify"
                        clean_title = full_title.split("|")[0].replace("song and lyrics by", "").strip()
                        return clean_title
            except Exception as e:
                logging.error(f"Spotify scrape error: {e}")
        return None

    @commands.hybrid_command(name="play", description="Воспроизвести музыку (YouTube/Spotify/Название)")
    async def play(self, ctx, *, search: str):
        if not await self.check_channel(ctx):
            return

        if not getattr(ctx.author, 'voice', None):
            await ctx.send(embed=discord.Embed(description="❌ Ты должен быть в голосовом канале!", color=COLOR_ERROR))
            return
            
        await ctx.defer()

        voice_client = ctx.voice_client
        if not voice_client:
            voice_client = await ctx.author.voice.channel.connect()

        # Проверка на Спотифай
        if "spotify.com/track" in search:
            await ctx.send(embed=discord.Embed(description="🔍 Парсим Spotify...", color=COLOR_SUCCESS))
            spotify_title = await self.get_spotify_track_info(search)
            if spotify_title:
                search = f"ytsearch:{spotify_title}"
            else:
                await ctx.send(embed=discord.Embed(description="❌ Не удалось прочитать Spotify трек.", color=COLOR_ERROR))
                return
        elif not search.startswith("http"):
            search = f"ytsearch:{search}"

        try:
            player = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True)
            if voice_client.is_playing():
                if ctx.guild.id not in self.queues:
                    self.queues[ctx.guild.id] = []
                self.queues[ctx.guild.id].append(search)
                queue_len = len(self.queues[ctx.guild.id])
                await ctx.send(embed=discord.Embed(description=f"🎵 Добавлено в очередь: **{player.title}**\n*(Треков в очереди: {queue_len})*", color=COLOR_SUCCESS))
            else:
                voice_client.play(player, after=lambda e: self.play_next(ctx))
                await ctx.send(embed=discord.Embed(description=f"▶️ Сейчас играет: **{player.title}**", color=COLOR_SUCCESS))
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"❌ Ошибка при загрузке: {e}", color=COLOR_ERROR))

    def play_next(self, ctx):
        if ctx.guild.id in self.queues and len(self.queues[ctx.guild.id]) > 0:
            next_song = self.queues[ctx.guild.id].pop(0)
            coro = YTDLSource.from_url(next_song, loop=self.bot.loop, stream=True)
            fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            try:
                player = fut.result()
            except Exception as e:
                logging.error(e)
                coro_msg = ctx.send(embed=discord.Embed(description=f"❌ Пропуск битого трека: {e}", color=COLOR_ERROR))
                asyncio.run_coroutine_threadsafe(coro_msg, self.bot.loop)
                self.play_next(ctx)
                return

            ctx.voice_client.play(player, after=lambda e: self.play_next(ctx))
            
            # Send message to channel where command was executed
            coro_msg = ctx.send(embed=discord.Embed(description=f"▶️ Сейчас играет: **{player.title}**", color=COLOR_SUCCESS))
            asyncio.run_coroutine_threadsafe(coro_msg, self.bot.loop)
        else:
            if ctx.voice_client:
                asyncio.run_coroutine_threadsafe(ctx.voice_client.disconnect(), self.bot.loop)
                coro_msg = ctx.send(embed=discord.Embed(description="⏹️ Очередь пуста, я покинул канал.", color=COLOR_SUCCESS))
                asyncio.run_coroutine_threadsafe(coro_msg, self.bot.loop)

    @commands.hybrid_command(name="skip", description="Пропустить текущий трек")
    async def skip(self, ctx):
        if not await self.check_channel(ctx):
            return

        await ctx.defer()
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send(embed=discord.Embed(description="⏭️ Трек пропущен.", color=COLOR_SUCCESS))
            
    @commands.hybrid_command(name="stop", description="Остановить музыку и выгнать бота")
    async def stop(self, ctx):
        if not await self.check_channel(ctx):
            return

        await ctx.defer()
        if ctx.voice_client:
            self.queues[ctx.guild.id] = []
            await ctx.voice_client.disconnect()
            await ctx.send(embed=discord.Embed(description="⏹️ Бот покинул канал.", color=COLOR_SUCCESS))

async def setup(bot):
    await bot.add_cog(Music(bot))
