import discord
from discord.ext import commands
from discord.ui import View, Button
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
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
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
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False, process=True))
        except Exception as e:
            logging.error(f"YTDL extract error: {e}")
            return None
        
        if data is None:
            return None
        
        if 'entries' in data and data['entries']:
            data = data['entries'][0]

        filename = data.get('url') or ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)

class GuildState:
    def __init__(self):
        self.queue = [] 
        self.current_track = None 
        self.repeat = False
        self.message_channel = None
        self.controls_msg = None

class MusicControlView(View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ Зайдите в голосовой канал!", ephemeral=True)
            return False
        vc = interaction.guild.voice_client
        if vc and interaction.user.voice.channel != vc.channel:
            await interaction.response.send_message(f"❌ Нужно быть в канале с ботом!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Пауза", emoji="⏯️", style=discord.ButtonStyle.secondary)
    async def play_pause(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if not vc: return
        if vc.is_playing():
            vc.pause()
            button.label = "Играть"
        elif vc.is_paused():
            vc.resume()
            button.label = "Пауза"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Пропуск", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if vc:
            state = self.cog.get_state(self.guild_id)
            state.repeat = False
            vc.stop()
            await interaction.response.defer()

    @discord.ui.button(label="Повтор", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def repeat(self, interaction: discord.Interaction, button: Button):
        state = self.cog.get_state(self.guild_id)
        state.repeat = not state.repeat
        button.style = discord.ButtonStyle.primary if state.repeat else discord.ButtonStyle.secondary
        title = state.current_track['title'] if state.current_track else "Ничего не играет"
        await interaction.response.edit_message(embed=self.cog.create_embed(state, title), view=self)

    @discord.ui.button(label="Стоп", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: Button):
        state = self.cog.get_state(self.guild_id)
        vc = interaction.guild.voice_client
        if vc:
            state.queue = []
            state.current_track = None
            await vc.disconnect()
            await interaction.response.edit_message(content="⏹️ Плеер остановлен.", embed=None, view=None)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.states = {}

    def get_state(self, guild_id):
        if guild_id not in self.states:
            self.states[guild_id] = GuildState()
        return self.states[guild_id]

    async def get_spotify_track_info(self, url):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    html = await response.text()
                    match = re.search(r'<title>(.+?)</title>', html)
                    if match:
                        full_title = match.group(1)
                        # Track Title - song by Artist | Spotify
                        clean_title = full_title.split("|")[0].replace("song and lyrics by", "").strip()
                        return clean_title
            except Exception as e:
                logging.error(f"Spotify parse error: {e}")
        return None

    def create_embed(self, state, title):
        embed = discord.Embed(title="🎵 Плеер", description=f"▶️ **{title}**", color=COLOR_SUCCESS)
        embed.add_field(name="В очереди", value=f"{len(state.queue)} треков", inline=True)
        embed.add_field(name="Повтор", value="✅ Вкл" if state.repeat else "❌ Выкл", inline=True)
        return embed

    async def update_controls(self, guild_id, title=None):
        state = self.get_state(guild_id)
        if not state.message_channel or not state.current_track: return
        embed = self.create_embed(state, title or state.current_track['title'])
        view = MusicControlView(self, guild_id)
        if state.controls_msg:
            try:
                await state.controls_msg.edit(embed=embed, view=view)
                return
            except: pass
        state.controls_msg = await state.message_channel.send(embed=embed, view=view)

    @commands.hybrid_command(name="play", description="Играть музыку/плейлист")
    async def play(self, ctx, *, search: str):
        if not getattr(ctx.author, 'voice', None):
            return await ctx.send("❌ Зайди в голосовой канал!", ephemeral=True)
            
        await ctx.defer()
        state = self.get_state(ctx.guild.id)
        state.message_channel = ctx.channel
        vc = ctx.voice_client or await ctx.author.voice.channel.connect()

        # Обработка Spotify
        if "spotify.com/track" in search:
            await ctx.send("🔍 Парсим Spotify...", delete_after=5)
            s_title = await self.get_spotify_track_info(search)
            if s_title:
                search = f"ytsearch:{s_title}"
            else:
                return await ctx.send("❌ Не удалось получить информацию из Spotify.", delete_after=10)
        elif not search.startswith("http"):
            search = f"ytsearch:{search}"

        # Умные лимиты
        active_users = set(t['user_id'] for t in state.queue)
        if state.current_track: active_users.add(state.current_track['user_id'])
        is_alone = len(active_users) <= 1 and (not active_users or ctx.author.id in active_users)
        playlist_limit = 50 if is_alone else 5

        try:
            data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False, process=False))
            
            if data is None:
                return await ctx.send("❌ Ничего не найдено.", delete_after=10)
            
            tracks_to_add = []
            if 'entries' in data and data['entries']:
                entries = list(data['entries'])
                added_count = 0
                for entry in entries:
                    if not entry: continue
                    if added_count >= playlist_limit: break
                    url = entry.get('url') or entry.get('webpage_url')
                    if not url and 'id' in entry: url = f"https://www.youtube.com/watch?v={entry['id']}"
                    if url:
                        tracks_to_add.append({'url': url, 'title': entry.get('title', 'Без названия'), 'user_id': ctx.author.id})
                        added_count += 1
                if 'ytsearch' not in search and "entries" in data:
                    await ctx.send(f"✅ Добавлено **{added_count}** треков. (Лимит: {playlist_limit})", delete_after=10)
            else:
                url = data.get('url') or data.get('webpage_url') or search
                tracks_to_add.append({'url': url, 'title': data.get('title', 'Без названия'), 'user_id': ctx.author.id})

            if not tracks_to_add:
                return await ctx.send("❌ Не удалось получить информацию о треках.", delete_after=10)

            for track in tracks_to_add:
                if not vc.is_playing() and not vc.is_paused() and not state.current_track:
                    state.current_track = track
                    player = await YTDLSource.from_url(track['url'], loop=self.bot.loop, stream=True)
                    if player:
                        vc.play(player, after=lambda e: self.play_next(ctx))
                        await self.update_controls(ctx.guild.id, player.title)
                    else:
                        state.current_track = None
                else:
                    state.queue.append(track)
            
            if len(tracks_to_add) == 1 and 'ytsearch' not in search:
                await ctx.send(f"➕ Добавлено: **{tracks_to_add[0]['title']}**", delete_after=10)
            
            if state.current_track:
                await self.update_controls(ctx.guild.id)

        except Exception as e:
            logging.error(f"Play error: {e}")
            await ctx.send(f"❌ Произошла ошибка при поиске.")

    def play_next(self, ctx):
        state = self.get_state(ctx.guild.id)
        vc = ctx.voice_client
        if not vc: return

        next_track = None
        if state.repeat: next_track = state.current_track
        elif state.queue: next_track = state.queue.pop(0)

        if next_track:
            state.current_track = next_track
            coro = YTDLSource.from_url(next_track['url'], loop=self.bot.loop, stream=True)
            fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            try:
                player = fut.result()
                if player:
                    vc.play(player, after=lambda e: self.play_next(ctx))
                    asyncio.run_coroutine_threadsafe(self.update_controls(ctx.guild.id, player.title), self.bot.loop)
                else:
                    self.play_next(ctx)
            except:
                self.play_next(ctx)
        else:
            state.current_track = None
            asyncio.run_coroutine_threadsafe(vc.disconnect(), self.bot.loop)
            if state.controls_msg:
                asyncio.run_coroutine_threadsafe(state.controls_msg.edit(content="⏹️ Очередь пуста.", embed=None, view=None), self.bot.loop)

async def setup(bot):
    await bot.add_cog(Music(bot))
