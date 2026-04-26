import discord
from discord.ext import commands
from discord.ui import View, Button
import yt_dlp
import asyncio
import aiohttp
import re
import logging
import time
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

class GuildState:
    def __init__(self):
        self.queue = []
        self.current_track = None  
        self.current_title = "Ничего не играет"
        self.repeat_mode = 0  # 0: Off, 1: Single, 2: Queue
        self.message_channel = None
        self.controls_msg = None

    def toggle_repeat(self):
        self.repeat_mode = (self.repeat_mode + 1) % 3
        return self.repeat_mode

class MusicControlView(View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Проверяем, находится ли пользователь в голосовом канале
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Вы должны быть в голосовом канале, чтобы управлять музыкой!", ephemeral=True)
            return False
        
        # Проверяем, находится ли пользователь в том же канале, что и бот
        vc = interaction.guild.voice_client
        if vc and interaction.user.voice.channel != vc.channel:
            await interaction.response.send_message(f"❌ Вы должны быть в канале {vc.channel.mention}, чтобы управлять плеером!", ephemeral=True)
            return False
            
        return True

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.secondary)
    async def play_pause(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if not vc: return
        
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Пауза", ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Возобновлено", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ничего не играет", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭️ Пропущено", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Нечего пропускать", ephemeral=True)

    @discord.ui.button(emoji="🔄", style=discord.ButtonStyle.secondary)
    async def repeat(self, interaction: discord.Interaction, button: Button):
        state = self.cog.get_state(self.guild_id)
        mode = state.toggle_repeat()
        modes = {0: "Выкл", 1: "Трек", 2: "Очередь"}
        await interaction.response.send_message(f"🔄 Повтор: **{modes[mode]}**", ephemeral=True)
        # Можно обновить эмбед если нужно

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: Button):
        state = self.cog.get_state(self.guild_id)
        vc = interaction.guild.voice_client
        if vc:
            state.queue = []
            state.current_track = None
            await vc.disconnect()
            await interaction.response.send_message("⏹️ Остановлено", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Бот не в канале", ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.states = {}

    def get_state(self, guild_id):
        if guild_id not in self.states:
            self.states[guild_id] = GuildState()
        return self.states[guild_id]

    async def check_channel(self, ctx):
        channel_name = ctx.channel.name.lower()
        if "музыка" not in channel_name and "music" not in channel_name:
            music_channel = discord.utils.get(ctx.guild.text_channels, name="🎵┃музыка")
            if not music_channel:
                music_channel = discord.utils.get(ctx.guild.text_channels, name="музыка")
            hint = f" в канале {music_channel.mention}" if music_channel else ""
            await ctx.send(f"❌ Команды только{hint}!", ephemeral=True)
            return False
        return True

    async def get_spotify_track_info(self, url):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    html = await response.text()
                    match = re.search(r'<title>(.+?)</title>', html)
                    if match:
                        return match.group(1).split("|")[0].replace("song and lyrics by", "").strip()
            except: pass
        return None

    def create_embed(self, state, title, color=COLOR_SUCCESS):
        modes = {0: "❌ Выкл", 1: "🔂 Трек", 2: "🔁 Очередь"}
        embed = discord.Embed(title="🎵 Музыкальный плеер", description=f"▶️ **{title}**", color=color)
        embed.add_field(name="Очередь", value=f"{len(state.queue)} треков", inline=True)
        embed.add_field(name="Повтор", value=modes[state.repeat_mode], inline=True)
        return embed

    @commands.hybrid_command(name="play", description="Играть музыку")
    async def play(self, ctx, *, search: str):
        if not await self.check_channel(ctx): return
        if not getattr(ctx.author, 'voice', None):
            return await ctx.send("❌ Зайди в голосовой канал!", ephemeral=True)
            
        await ctx.defer()
        state = self.get_state(ctx.guild.id)
        state.message_channel = ctx.channel

        vc = ctx.voice_client or await ctx.author.voice.channel.connect()

        if "spotify.com/track" in search:
            s_title = await self.get_spotify_track_info(search)
            if s_title: search = f"ytsearch:{s_title}"
            else: return await ctx.send("❌ Ошибка Spotify")
        elif not search.startswith("http"):
            search = f"ytsearch:{search}"

        try:
            player = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True)
            if vc.is_playing() or vc.is_paused():
                state.queue.append(search)
                await ctx.send(f"➕ Добавлено: **{player.title}**")
            else:
                state.current_track = search
                state.current_title = player.title
                vc.play(player, after=lambda e: self.play_next(ctx))
                view = MusicControlView(self, ctx.guild.id)
                state.controls_msg = await ctx.send(embed=self.create_embed(state, player.title), view=view)
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}")

    def play_next(self, ctx):
        state = self.get_state(ctx.guild.id)
        vc = ctx.voice_client
        if not vc: return

        next_song = None
        if state.repeat_mode == 1: next_song = state.current_track
        elif state.repeat_mode == 2:
            if state.current_track: state.queue.append(state.current_track)
            if state.queue: next_song = state.queue.pop(0)
        else:
            if state.queue: next_song = state.queue.pop(0)

        if next_song:
            state.current_track = next_song
            coro = YTDLSource.from_url(next_song, loop=self.bot.loop, stream=True)
            fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            try:
                player = fut.result()
                state.current_title = player.title
                vc.play(player, after=lambda e: self.play_next(ctx))
                view = MusicControlView(self, ctx.guild.id)
                coro_msg = state.message_channel.send(embed=self.create_embed(state, player.title), view=view)
                asyncio.run_coroutine_threadsafe(coro_msg, self.bot.loop)
            except:
                self.play_next(ctx)
        else:
            state.current_track = None
            asyncio.run_coroutine_threadsafe(vc.disconnect(), self.bot.loop)
            coro_msg = state.message_channel.send("⏹️ Очередь пуста.")
            asyncio.run_coroutine_threadsafe(coro_msg, self.bot.loop)

    @commands.hybrid_command(name="repeat", description="Режим повтора")
    async def repeat(self, ctx):
        state = self.get_state(ctx.guild.id)
        mode = state.toggle_repeat()
        modes = {0: "Выкл", 1: "Один трек", 2: "Вся очередь"}
        await ctx.send(f"🔄 Повтор: **{modes[mode]}**")

    @commands.hybrid_command(name="skip", description="Пропустить")
    async def skip(self, ctx):
        if ctx.voice_client:
            ctx.voice_client.stop()
            await ctx.send("⏭️ Пропущено")

    @commands.hybrid_command(name="stop", description="Стоп")
    async def stop(self, ctx):
        state = self.get_state(ctx.guild.id)
        if ctx.voice_client:
            state.queue = []
            await ctx.voice_client.disconnect()
            await ctx.send("⏹️ Остановлено")

async def setup(bot):
    await bot.add_cog(Music(bot))
