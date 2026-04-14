import discord
from discord.ext import commands
import aiohttp
import os
import asyncio
import urllib.parse
import re
from config import COLOR_SUCCESS, COLOR_ERROR

class Cinema(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Удаляем лишний слэш в конце URL
        url = os.getenv("TORRSERVER_URL", "")
        self.ts_url = url.rstrip('/') 
        self.ts_user = os.getenv("TORRSERVER_USER")
        self.ts_pass = os.getenv("TORRSERVER_PASS")
        # Твой личный ID приложения
        self.activity_id = 1493748753587376310 

    async def search_torrents(self, query):
        """Улучшенный поиск торрентов с фильтрацией инфо-мусора"""
        async with aiohttp.ClientSession() as session:
            try:
                search_query = urllib.parse.quote(query)
                url = f"https://rutor.info/search/0/0/000/0/{search_query}"
                headers = {'User-Agent': 'Mozilla/5.0'}
                
                async with session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status != 200:
                        return []
                    html = await resp.text()
                    
                    magnets = re.findall(r'href="(magnet:\?xt=urn:btih:[^"]+)"', html)
                    titles = re.findall(r'<a href="/torrent/.*?">(.*?)</a>', html)
                    
                    results = []
                    for i in range(min(len(magnets), 20)): # Берем побольше для фильтрации
                        title = titles[i].replace("<b>", "").replace("</b>", "")
                        # Фильтруем служебные ссылки Rutor
                        trash_keywords = ["rutor.info", "rutor.is", "правила", "путеводитель", "адрес", "блокировка"]
                        if any(word in title.lower() for word in trash_keywords):
                            continue
                            
                        results.append((magnets[i], title))
                        if len(results) >= 5: # Нам нужно только 5 чистых результатов
                            break
                    return results
            except Exception as e:
                print(f"Search error: {e}")
                return []

    async def add_to_torrserver(self, magnet):
        """Добавление в TorrServer с фиксом двойных слэшей"""
        auth = aiohttp.BasicAuth(self.ts_user, self.ts_pass)
        async with aiohttp.ClientSession(auth=auth) as session:
            try:
                data = {"action": "add", "link": magnet, "save": True}
                # Самостоятельно формируем URL без лишних слэшей
                api_url = f"{self.ts_url}/torrents"
                async with session.post(api_url, json=data) as resp:
                    if resp.status != 200:
                        return None
                    res = await resp.json()
                    return res.get("hash")
            except Exception as e:
                print(f"TorrServer error: {e}")
                return None

    @commands.hybrid_command(name="cinema", description="Найти фильм и запустить в твоем плеере")
    async def cinema(self, ctx, *, query: str):
        if not ctx.author.voice:
            return await ctx.send(embed=discord.Embed(description="❌ Зайди в голосовой канал!", color=COLOR_ERROR))

        await ctx.defer()
        
        results = await self.search_torrents(query)
        if not results:
            return await ctx.send(embed=discord.Embed(description="❌ По этому запросу ничего не найдено.", color=COLOR_ERROR))

        embed = discord.Embed(
            title="🎥 Кинотеатр mriamys",
            description=f"Найденные раздачи для: **{query}**\nВыбери вариант для загрузки в плеер:",
            color=COLOR_SUCCESS
        )

        class CinemaSelect(discord.ui.View):
            def __init__(self, cinema_cog, results, author):
                super().__init__(timeout=60)
                self.cog = cinema_cog
                self.results = results
                self.author = author

            @discord.ui.select(
                placeholder="Выбери качество/раздачу...",
                options=[
                    discord.SelectOption(label=f"Вариант {i+1}", description=res[1][:100], value=str(i))
                    for i, res in enumerate(results)
                ]
            )
            async def select_callback(self, interaction, select):
                if interaction.user != self.author:
                    return await interaction.response.send_message("Это не твое меню!", ephemeral=True)
                
                await interaction.response.defer()
                idx = int(select.values[0])
                magnet, title = self.results[idx]
                
                movie_hash = await self.cog.add_to_torrserver(magnet)
                if not movie_hash:
                    return await interaction.followup.send(f"❌ Ошибка связи с TorrServer. Проверь `.env`.\n*Убедись, что адрес {self.cog.ts_url} доступен с VPS.*")

                # Создаем Activity инвайт
                invite = await self.author.voice.channel.create_invite(
                    target_type=discord.InviteTarget.embedded_application,
                    target_application_id=self.cog.activity_id
                )

                finish_embed = discord.Embed(
                    title=f"🎬 Фильм добавлен!",
                    description=(
                        f"**Название:** {title[:100]}\n\n"
                        "**Инструкция:**\n"
                        "1. Нажми кнопку **🚀 Запустить кино**.\n"
                        "2. В открывшемся окне Дискорда найди этот фильм и нажми Play."
                    ),
                    color=COLOR_SUCCESS
                )
                
                final_view = discord.ui.View()
                final_view.add_item(discord.ui.Button(label="🚀 Запустить кино", url=invite.url))
                await interaction.followup.send(embed=finish_embed, view=final_view)

        await ctx.send(embed=embed, view=CinemaSelect(self, results, ctx.author))

async def setup(bot):
    await bot.add_cog(Cinema(bot))
