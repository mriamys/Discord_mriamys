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
        if 'entries' in data: data = data['entries'][0]
        duration = data.get('duration', 0)
        if duration and duration > 600:
            raise ValueError(f"Трек слишком длинный. Максимум — 10 минут!")
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)

class GuildState:
    def __init__(self):
        self.queue = []
        self.current_track = None  
        self.current_title = "Ничего не играет"
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
            await interaction.response.edit_message(view=self)
        elif vc.is_paused():
            vc.resume()
            button.label = "Пауза"
            await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Пропуск", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if vc:
            # Отключаем повтор при пропуске, чтобы не зациклило этот же трек
            state = self.cog.get_state(self.guild_id)
            state.repeat = False
            vc.stop()
            await interaction.response.defer()

    @discord.ui.button(label="Повтор: Выкл", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def repeat(self, interaction: discord.Interaction, button: Button):
        state = self.cog.get_state(self.guild_id)
        state.repeat = not state.repeat
        button.label = f"Повтор: {'Вкл' if state.repeat else 'Выкл'}"
        button.style = discord.ButtonStyle.primary if state.repeat else discord.ButtonStyle.secondary
        await interaction.response.edit_message(embed=self.cog.create_embed(state, state.current_title), view=self)

    @discord.ui.button(label="Стоп", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: Button):
        state = self.cog.get_state(self.guild_id)
        vc = interaction.guild.voice_client
        if vc:
            state.queue = []
            state.current_track = None
            await vc.disconnect()
            await interaction.response.edit_message(content="⏹️ Воспроизведение остановлено.", embed=None, view=None)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.states = {}

    def get_state(self, guild_id):
        if guild_id not in self.states:
            self.states[guild_id] = GuildState()
        return self.states[guild_id]

    def create_embed(self, state, title):
        embed = discord.Embed(title="🎵 Плеер", description=f"▶️ **{title}**", color=COLOR_SUCCESS)
        embed.add_field(name="В очереди", value=f"{len(state.queue)}", inline=True)
        embed.add_field(name="Повтор", value="✅ Вкл" if state.repeat else "❌ Выкл", inline=True)
        return embed

    async def update_controls(self, guild_id, title=None):
        state = self.get_state(guild_id)
        if not state.message_channel: return
        
        embed = self.create_embed(state, title or state.current_title)
        view = MusicControlView(self, guild_id)
        
        # Если сообщение уже есть, пробуем его редактировать
        if state.controls_msg:
            try:
                await state.controls_msg.edit(embed=embed, view=view)
                return
            except: pass
            
        state.controls_msg = await state.message_channel.send(embed=embed, view=view)

    @commands.hybrid_command(name="play", description="Играть музыку")
    async def play(self, ctx, *, search: str):
        if not getattr(ctx.author, 'voice', None):
            return await ctx.send("❌ Зайди в голосовой канал!", ephemeral=True)
            
        await ctx.defer()
        state = self.get_state(ctx.guild.id)
        state.message_channel = ctx.channel
        vc = ctx.voice_client or await ctx.author.voice.channel.connect()

        if not search.startswith("http"): search = f"ytsearch:{search}"

        try:
            player = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True)
            if vc.is_playing() or vc.is_paused():
                state.queue.append(search)
                await ctx.send(f"➕ Добавлено: **{player.title}**", delete_after=10)
                await self.update_controls(ctx.guild.id)
            else:
                state.current_track = search
                state.current_title = player.title
                vc.play(player, after=lambda e: self.play_next(ctx))
                await self.update_controls(ctx.guild.id, player.title)
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}")

    def play_next(self, ctx):
        state = self.get_state(ctx.guild.id)
        vc = ctx.voice_client
        if not vc: return

        next_song = None
        if state.repeat: next_song = state.current_track
        elif state.queue: next_song = state.queue.pop(0)

        if next_song:
            state.current_track = next_song
            coro = YTDLSource.from_url(next_song, loop=self.bot.loop, stream=True)
            fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            try:
                player = fut.result()
                state.current_title = player.title
                vc.play(player, after=lambda e: self.play_next(ctx))
                asyncio.run_coroutine_threadsafe(self.update_controls(ctx.guild.id, player.title), self.bot.loop)
            except:
                self.play_next(ctx)
        else:
            state.current_track = None
            asyncio.run_coroutine_threadsafe(vc.disconnect(), self.bot.loop)
            if state.controls_msg:
                asyncio.run_coroutine_threadsafe(state.controls_msg.edit(content="⏹️ Очередь пуста.", embed=None, view=None), self.bot.loop)

async def setup(bot):
    await bot.add_cog(Music(bot))
