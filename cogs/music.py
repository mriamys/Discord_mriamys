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
        self.duration = data.get('duration')
        self.uploader = data.get('uploader')
        self.thumbnail = data.get('thumbnail')

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
            # If bot is alone in channel, allow moving
            if len(vc.channel.members) == 1:
                await vc.move_to(interaction.user.voice.channel)
                return True
            await interaction.response.send_message(f"❌ Нужно быть в одном канале с ботом!", ephemeral=True)
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
    async def repeat_btn(self, interaction: discord.Interaction, button: Button):
        state = self.cog.get_state(self.guild_id)
        state.repeat = not state.repeat
        button.style = discord.ButtonStyle.primary if state.repeat else discord.ButtonStyle.secondary
        await interaction.response.edit_message(embed=self.cog.create_embed(state, state.current_track), view=self)

    @discord.ui.button(label="Стоп", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: Button):
        state = self.cog.get_state(self.guild_id)
        vc = interaction.guild.voice_client
        if vc:
            state.queue = []
            state.current_track = None
            await vc.disconnect()
            if state.controls_msg:
                try:
                    await state.controls_msg.delete()
                except: pass
                state.controls_msg = None
            await interaction.response.send_message("⏹️ Плеер остановлен.", ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.states = {}

    def get_state(self, guild_id):
        if guild_id not in self.states:
            self.states[guild_id] = GuildState()
        return self.states[guild_id]

    def format_duration(self, seconds):
        if not seconds: return "Стрим"
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    async def get_spotify_track_info(self, url):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    html = await response.text()
                    match = re.search(r'<title>(.+?)</title>', html)
                    if match:
                        full_title = match.group(1)
                        clean_title = full_title.split("|")[0].replace("song and lyrics by", "").strip()
                        return clean_title
            except Exception as e:
                logging.error(f"Spotify parse error: {e}")
        return None

    def create_embed(self, state, track_data):
        if not track_data:
            return discord.Embed(title="🎵 Плеер", description="Ничего не играет", color=COLOR_SUCCESS)
        
        title = track_data.get('title', 'Без названия')
        uploader = track_data.get('uploader', 'Неизвестно')
        duration = self.format_duration(track_data.get('duration'))
        thumbnail = track_data.get('thumbnail')
        requester = f"<@{track_data['user_id']}>" if 'user_id' in track_data else "Система"

        embed = discord.Embed(title="🎵 Сейчас играет", description=f"**[{title}]({track_data.get('url')})**", color=COLOR_SUCCESS)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        
        embed.add_field(name="👤 Автор", value=uploader, inline=True)
        embed.add_field(name="🕒 Длительность", value=duration, inline=True)
        embed.add_field(name="🎧 Заказал", value=requester, inline=True)
        
        queue_len = len(state.queue)
        embed.add_field(name="📜 Очередь", value=f"{queue_len} треков", inline=True)
        embed.add_field(name="🔄 Повтор", value="✅ Вкл" if state.repeat else "❌ Выкл", inline=True)
        
        return embed

    async def update_controls(self, guild_id, track_data=None):
        state = self.get_state(guild_id)
        if not state.message_channel: return
        
        current_data = track_data or state.current_track
        if not current_data: return

        embed = self.create_embed(state, current_data)
        view = MusicControlView(self, guild_id)
        
        if state.controls_msg:
            try:
                await state.controls_msg.edit(embed=embed, view=view)
                return
            except: 
                state.controls_msg = None
        
        state.controls_msg = await state.message_channel.send(embed=embed, view=view)

    @commands.hybrid_command(name="play", description="Играть музыку/плейлист")
    async def play(self, ctx, *, search: str):
        if not getattr(ctx.author, 'voice', None):
            return await ctx.send("❌ Зайди в голосовой канал!", ephemeral=True)
            
        await ctx.defer()
        state = self.get_state(ctx.guild.id)
        state.message_channel = ctx.channel
        
        vc = ctx.voice_client
        if not vc:
            vc = await ctx.author.voice.channel.connect()
        else:
            # Check if we should move immediately
            # Move if: bot is not playing OR current channel has no humans (other than bot)
            listeners = [m for m in vc.channel.members if not m.bot]
            if not vc.is_playing() or not listeners:
                if vc.channel != ctx.author.voice.channel:
                    await vc.move_to(ctx.author.voice.channel)

        if "spotify.com/track" in search:
            await ctx.send("🔍 Парсим Spotify...", delete_after=5)
            s_title = await self.get_spotify_track_info(search)
            if s_title: search = f"ytsearch:{s_title}"
            else: return await ctx.send("❌ Не удалось получить информацию из Spotify.")
        elif not search.startswith("http"):
            search = f"ytsearch:{search}"

        active_users = set(t['user_id'] for t in state.queue)
        if state.current_track: active_users.add(state.current_track['user_id'])
        is_alone = len(active_users) <= 1 and (not active_users or ctx.author.id in active_users)
        playlist_limit = 50 if is_alone else 5

        try:
            data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(search, download=False, process=False))
            if data is None: return await ctx.send("❌ Ничего не найдено.")
            
            tracks_to_add = []
            if 'entries' in data and data['entries']:
                # It's a playlist or search results
                is_search = data.get('_type') == 'playlist' and 'ytsearch' in search
                entries = list(data['entries'])
                
                if is_search:
                    # If it was a search, just take the first result
                    entry = entries[0]
                    url = entry.get('url') or entry.get('webpage_url') or f"https://www.youtube.com/watch?v={entry['id']}"
                    tracks_to_add.append({
                        'url': url, 
                        'title': entry.get('title', 'Без названия'), 
                        'uploader': entry.get('uploader', 'Неизвестно'),
                        'duration': entry.get('duration'),
                        'thumbnail': entry.get('thumbnail'),
                        'user_id': ctx.author.id
                    })
                else:
                    # It's a real playlist
                    added_count = 0
                    for entry in entries:
                        if not entry: continue
                        if added_count >= playlist_limit: break
                        url = entry.get('url') or entry.get('webpage_url') or f"https://www.youtube.com/watch?v={entry['id']}"
                        tracks_to_add.append({
                            'url': url, 
                            'title': entry.get('title', 'Без названия'), 
                            'uploader': entry.get('uploader', 'Неизвестно'),
                            'duration': entry.get('duration'),
                            'thumbnail': entry.get('thumbnail'),
                            'user_id': ctx.author.id
                        })
                        added_count += 1
            else:
                # Single track
                url = data.get('url') or data.get('webpage_url') or search
                tracks_to_add.append({
                    'url': url, 
                    'title': data.get('title', 'Без названия'), 
                    'uploader': data.get('uploader', 'Неизвестно'),
                    'duration': data.get('duration'),
                    'thumbnail': data.get('thumbnail'),
                    'user_id': ctx.author.id
                })

            if not tracks_to_add: return await ctx.send("❌ Не удалось найти треки.")

            # Auto-disable repeat when adding new tracks
            if state.repeat:
                state.repeat = False

            started_playing = False
            for track in tracks_to_add:
                if not vc.is_playing() and not vc.is_paused() and not state.current_track:
                    state.current_track = track
                    player = await YTDLSource.from_url(track['url'], loop=self.bot.loop, stream=True)
                    if player:
                        # Update current_track with more detailed info from player if available
                        state.current_track['title'] = player.title
                        state.current_track['uploader'] = player.uploader
                        state.current_track['duration'] = player.duration
                        state.current_track['thumbnail'] = player.thumbnail
                        
                        vc.play(player, after=lambda e: self.play_next(ctx, e))
                        await self.update_controls(ctx.guild.id)
                        started_playing = True
                    else: 
                        state.current_track = None
                else:
                    state.queue.append(track)
            
            if len(tracks_to_add) > 1:
                await ctx.send(f"✅ Добавлено **{len(tracks_to_add)}** треков. (Лимит: {playlist_limit})", delete_after=10)
            elif not started_playing:
                await ctx.send(f"➕ Добавлено в очередь: **{tracks_to_add[0]['title']}**", delete_after=10)
            
            if state.current_track: await self.update_controls(ctx.guild.id)

        except Exception as e:
            logging.error(f"Play error: {e}")
            await ctx.send(f"❌ Ошибка при поиске.")

    def play_next(self, ctx, error=None):
        if error:
            logging.error(f"Player error: {error}")
        # Run the async playback logic on the event loop, avoiding blocking the voice thread
        asyncio.run_coroutine_threadsafe(self.async_play_next(ctx), self.bot.loop)

    async def async_play_next(self, ctx):
        state = self.get_state(ctx.guild.id)
        vc = ctx.voice_client
        if not vc: return
        
        next_track = None
        if state.repeat and state.current_track: 
            next_track = state.current_track
        elif state.queue: 
            next_track = state.queue.pop(0)
            
        if next_track:
            state.current_track = next_track
            
            # Smart move: if requester is in a different voice channel, move there
            user_id = next_track.get('user_id')
            if user_id:
                guild = self.bot.get_guild(ctx.guild.id)
                member = guild.get_member(user_id)
                if member and member.voice and member.voice.channel:
                    if vc.channel != member.voice.channel:
                        # Move to requester's channel
                        await vc.move_to(member.voice.channel)

            try:
                player = await YTDLSource.from_url(next_track['url'], loop=self.bot.loop, stream=True)
                if player:
                    state.current_track['title'] = player.title
                    state.current_track['uploader'] = player.uploader
                    state.current_track['duration'] = player.duration
                    state.current_track['thumbnail'] = player.thumbnail
                    
                    vc.play(player, after=lambda e: self.play_next(ctx, e))
                    await self.update_controls(ctx.guild.id)
                else: 
                    self.play_next(ctx)
            except Exception as e:
                logging.error(f"Play next error: {e}")
                self.play_next(ctx)
        else:
            state.current_track = None
            if vc.is_connected():
                await vc.disconnect()
            if state.controls_msg:
                try:
                    await state.controls_msg.edit(content="⏹️ Очередь пуста.", embed=None, view=None)
                except:
                    pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id == self.bot.user.id and after.channel is None:
            # Bot was disconnected
            state = self.get_state(member.guild.id)
            state.queue = []
            state.current_track = None
            if state.controls_msg:
                try: await state.controls_msg.delete()
                except: pass
                state.controls_msg = None

    @commands.hybrid_command(name="queue", description="Показать очередь воспроизведения")
    async def queue(self, ctx):
        state = self.get_state(ctx.guild.id)
        if not state.queue and not state.current_track:
            return await ctx.send("Очередь пуста.")
        
        embed = discord.Embed(title="📜 Очередь воспроизведения", color=COLOR_SUCCESS)
        if state.current_track:
            embed.add_field(name="▶️ Сейчас играет", value=state.current_track.get('title', 'Без названия'), inline=False)
        
        if state.queue:
            queue_list = ""
            for i, track in enumerate(state.queue[:10], 1):
                queue_list += f"{i}. {track.get('title', 'Без названия')}\n"
            if len(state.queue) > 10:
                queue_list += f"... и еще {len(state.queue) - 10} треков"
            embed.add_field(name="📋 Будущие треки", value=queue_list, inline=False)
        else:
            embed.add_field(name="📋 Будущие треки", value="Очередь пуста", inline=False)
            
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="stop", description="Остановить плеер и очистить очередь")
    async def stop_cmd(self, ctx):
        state = self.get_state(ctx.guild.id)
        vc = ctx.voice_client
        if vc:
            state.queue = []
            state.current_track = None
            await vc.disconnect()
            await ctx.send("⏹️ Плеер остановлен, очередь очищена.")
        else:
            await ctx.send("❌ Бот не в голосовом канале.")

async def setup(bot):
    await bot.add_cog(Music(bot))
