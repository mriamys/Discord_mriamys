import discord
from discord.ext import commands
import aiohttp
import os
import urllib.parse
import re
import logging
from config import COLOR_SUCCESS, COLOR_ERROR

# Используем стандартный логгер
logger = logging.getLogger('root')

class Cinema(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        url = os.getenv("TORRSERVER_URL", "")
        self.ts_url = url.rstrip('/') 
        self.ts_user = os.getenv("TORRSERVER_USER", "")
        self.ts_pass = os.getenv("TORRSERVER_PASS", "")
        self.activity_id = 1493748753587376310 

    async def search_torrents(self, query):
        async with aiohttp.ClientSession() as session:
            try:
                search_query = urllib.parse.quote(query)
                url = f"https://rutor.info/search/0/0/000/0/{search_query}"
                headers = {'User-Agent': 'Mozilla/5.0'}
                async with session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status != 200: return []
                    html = await resp.text()
                    magnets = re.findall(r'href="(magnet:\?xt=urn:btih:[^"]+)"', html)
                    titles = re.findall(r'<a href="/torrent/.*?">(.*?)</a>', html)
                    results = []
                    for i in range(min(len(magnets), 20)):
                        title = titles[i].replace("<b>", "").replace("</b>", "")
                        if any(word in title.lower() for word in ["rutor.info", "rutor.is", "правила", "путеводитель"]): continue
                        results.append((magnets[i], title))
                        if len(results) >= 5: break
                    return results
            except Exception as e:
                logger.error(f"Search error: {e}")
                return []

    async def add_to_torrserver(self, magnet):
        auth = None
        if self.ts_user and self.ts_pass:
            auth = aiohttp.BasicAuth(self.ts_user, self.ts_pass)

        timeout = aiohttp.ClientTimeout(total=7)
        async with aiohttp.ClientSession(auth=auth, timeout=timeout) as session:
            data = {"action": "add", "link": magnet, "save": True}
            
            # Пробуем Localhost и Внешний URL
            urls = ["http://127.0.0.1:8090/torrents", f"{self.ts_url}/torrents"]
            errors = []
            
            for url in urls:
                if not url.startswith("http"): continue
                try:
                    async with session.post(url, json=data) as resp:
                        if resp.status == 200:
                            return True, await resp.json()
                        errors.append(f"{url} -> HTTP {resp.status}")
                except Exception as e:
                    errors.append(f"{url} -> {type(e).__name__}")
            
            return False, "; ".join(errors)

    @commands.hybrid_command(name="cinema", description="Поиск и запуск кино")
    async def cinema(self, ctx, *, query: str):
        if not ctx.author.voice:
            return await ctx.send(embed=discord.Embed(description="❌ Зайди в голосовой канал!", color=COLOR_ERROR))

        await ctx.defer()
        results = await self.search_torrents(query)
        if not results:
            return await ctx.send(embed=discord.Embed(description="❌ Ничего не найдено.", color=COLOR_ERROR))

        view = CinemaSelectView(self, results, ctx.author)
        embed = discord.Embed(title="🎥 Кинотеатр", description=f"Результаты для: **{query}**", color=COLOR_SUCCESS)
        await ctx.send(embed=embed, view=view)

class CinemaSelectView(discord.ui.View):
    def __init__(self, cog, results, author):
        super().__init__(timeout=60)
        self.cog = cog
        self.results = results
        self.author = author

    @discord.ui.select(
        placeholder="Выбери фильм...",
        options=[discord.SelectOption(label=f"Вариант {i+1}", description=res[1][:100], value=str(i)) for i, res in enumerate(results)]
    )
    async def select_callback(self, interaction, select):
        if interaction.user != self.author: return
        await interaction.response.defer()
        
        idx = int(select.values[0])
        magnet, title = self.results[idx]
        
        success, info = await self.cog.add_to_torrserver(magnet)
        
        if not success:
            # Выводим конкретную ошибку прямо в Дискорд
            err_msg = f"❌ **Ошибка TorrServer:**\n`{info}`\n\nПроверь, что сервер запущен и пароль верен."
            return await interaction.followup.send(err_msg)

        invite = await self.author.voice.channel.create_invite(
            target_type=discord.InviteTarget.embedded_application,
            target_application_id=self.cog.activity_id
        )

        final_embed = discord.Embed(
            title="🎬 Фильм готов!",
            description=f"**{title[:100]}** удачно добавлен.\n\nЖми кнопку и выбирай его в списке!",
            color=COLOR_SUCCESS
        )
        btn_view = discord.ui.View()
        btn_view.add_item(discord.ui.Button(label="🚀 Запустить кино", url=invite.url))
        await interaction.followup.send(embed=final_embed, view=btn_view)

async def setup(bot):
    await bot.add_cog(Cinema(bot))
