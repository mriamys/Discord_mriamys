import discord
from discord.ext import commands
import aiohttp
from aiohttp import web
import os
import urllib.parse
import re
import logging
import asyncio
from config import COLOR_SUCCESS, COLOR_ERROR

logger = logging.getLogger('Cinema')

class Cinema(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ts_url = os.getenv("TORRSERVER_URL", "").rstrip('/') 
        self.ts_user = os.getenv("TORRSERVER_USER", "")
        self.ts_pass = os.getenv("TORRSERVER_PASS", "")
        self.activity_id = 1493748753587376310 
        
        # Для Синхронизации (WebSockets)
        self.ws_clients = set()
        self.app = web.Application()
        self.app.router.add_get('/ws', self.websocket_handler)
        self.runner = web.AppRunner(self.app)
        self.site = None
        self.bot.loop.create_task(self.start_ws_server())

    async def start_ws_server(self):
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '0.0.0.0', 8765)
        await self.site.start()
        logger.info("Cinema Sync WebSocket Server started on port 8765")

    async def cog_unload(self):
        if self.site:
            self.bot.loop.create_task(self.runner.cleanup())

    async def websocket_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.ws_clients.add(ws)
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    # Ретранслируем сообщение всем остальным участникам
                    for client in self.ws_clients:
                        if client != ws and not client.closed:
                            await client.send_str(msg.data)
        except Exception as e:
            pass
        finally:
            self.ws_clients.remove(ws)
        return ws 

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

        # Локальный и внешний адреса
        urls = ["http://127.0.0.1:8090/torrents", f"{self.ts_url}/torrents"]
        errors = []

        async with aiohttp.ClientSession(auth=auth, timeout=aiohttp.ClientTimeout(total=8)) as session:
            data = {"action": "add", "link": magnet, "save": True}
            for url in urls:
                if not url.startswith("http"): continue
                try:
                    async with session.post(url, json=data) as resp:
                        if resp.status == 200:
                            return True, await resp.json()
                        errors.append(f"{url} -> HTTP {resp.status}")
                except Exception as e:
                    errors.append(f"{url} -> {type(e).__name__}")
            return False, " | ".join(errors)

    @commands.hybrid_command(name="cinema", description="Поиск и онлайн просмотр фильмов")
    async def cinema(self, ctx, *, query: str):
        if not ctx.author.voice:
            return await ctx.send(embed=discord.Embed(description="❌ Зайди в голосовой канал!", color=COLOR_ERROR))

        await ctx.defer()
        results = await self.search_torrents(query)
        if not results:
            return await ctx.send(embed=discord.Embed(description=f"❌ Ничего не найдено: {query}", color=COLOR_ERROR))

        embed = discord.Embed(title="🎥 Выбор раздачи", description="Выбери версию фильма для загрузки:", color=COLOR_SUCCESS)
        # Передаем результаты в View
        view = CinemaSelectView(self, results, ctx.author)
        await ctx.send(embed=embed, view=view)

class CinemaSelectView(discord.ui.View):
    def __init__(self, cog, results, author):
        super().__init__(timeout=60)
        self.cog = cog
        self.results = results
        self.author = author
        
        # Динамически создаем Select и добавляем его
        select = discord.ui.Select(
            placeholder="Выберите фильм из списка...",
            options=[
                discord.SelectOption(label=f"Фильм #{i+1}", description=res[1][:100], value=str(i))
                for i, res in enumerate(results)
            ]
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("Это не твое меню!", ephemeral=True)
            
        await interaction.response.defer()
        # Значение лежит в первом элементе списка values самого селекта (мы его добавили последним)
        select_obj = self.children[0]
        idx = int(select_obj.values[0])
        magnet, title = self.results[idx]
        success, info = await self.cog.add_to_torrserver(magnet)
        
        if not success:
            return await interaction.followup.send(f"❌ **Ошибка TorrServer:**\n`{info}`")

        invite = await self.author.voice.channel.create_invite(
            target_type=discord.InviteTarget.embedded_application,
            target_application_id=self.cog.activity_id
        )

        hash_code = info.get('hash') if isinstance(info, dict) else None
        # Ссылка на наш новый плеер
        player_url = f"{self.cog.ts_url}/player.html?hash={hash_code}"

        final_embed = discord.Embed(
            title="🎬 Готово к просмотру!",
            description=f"Фильм: **{title[:100]}**\n\n1. Нажми **'Запустить активность'**.\n2. Если там белый экран, используй вторую кнопку ниже.",
            color=COLOR_SUCCESS
        )
        
        btn_view = discord.ui.View()
        btn_view.add_item(discord.ui.Button(label="🚀 Запустить активность", url=invite.url))
        btn_view.add_item(discord.ui.Button(label="🔗 Открыть в браузере", url=player_url))
        await interaction.followup.send(embed=final_embed, view=btn_view)

async def setup(bot):
    await bot.add_cog(Cinema(bot))
