import discord
from discord.ext import commands
from config import COLOR_MAIN

class CustomHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="help", aliases=["команды", "помощь"], description="Показать список всех команд бота")
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="🌌 Путеводитель по Mriamys",
            description="Добро пожаловать! Ниже представлен функционал бота. Большинство команд поддерживают как слэш `/команда`, так и префикс `!команда`.",
            color=COLOR_MAIN
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url if self.bot.user.avatar else None)
        
        embed.add_field(
            name="🎵 Музыка",
            value="`/play <запрос/url>` — Включить трек\n"
                  "`/skip` — Пропустить трек\n"
                  "`/pause` / `/resume` — Пауза и продолжение\n"
                  "`/queue` — Показать очередь\n"
                  "`/stop` — Очистить очередь и выгнать бота",
            inline=False
        )
        
        embed.add_field(
            name="💎 Статистика и Экономика",
            value="`/profile` — Твоя карточка профиля (уровень, опыт, коины)\n"
                  "`/stat` — Подробная текстовая статистика\n"
                  "`/top` — Посмотреть списки лидеров сервера\n"
                  "`/баланс` — Узнать свой текущий баланс VibeКоинов",
            inline=False
        )
        
        embed.add_field(
            name="🎲 Развлечения и Магазин",
            value="Все игры (Казино, Кейсы, Дуэли) и покупки привилегий (Мемы, Бусты, Роли) доступны **через удобные кнопки в специальном канале магазина**.\n"
                  "Отдельных команд для них вводить не нужно!",
            inline=False
        )        
        embed.set_footer(text="Mriamys Bot | Создано при поддержке Antigravity")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CustomHelp(bot))
