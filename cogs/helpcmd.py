import discord
from discord.ext import commands
from config import COLOR_MAIN

class CustomHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="help", aliases=["команды", "помощь"], description="Показать список всех команд бота")
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="📚 Список команд Mriamys",
            description="Вот все доступные команды, которые вы можете использовать:",
            color=COLOR_MAIN
        )
        
        embed.add_field(
            name="🎵 Музыка",
            value="`/play <название/ссылка>` — Включить трек (YouTube/Spotify)\n"
                  "`/skip` — Пропустить текущий трек\n"
                  "`/stop` — Остановить музыку и выгнать бота",
            inline=False
        )
        
        embed.add_field(
            name="💎 Экономика и Ранги",
            value="`/profile` (или `!profile`) — Твоя красивая карточка с вайб-коинами, опытом и часами в войсе\n"
                  "`/shop` — Магазин ролей за вайб-коины (покупай кастомные роли!)\n"
                  "`/inventory` — Твой инвентарь (кастомные роли)\n"
                  "`/buy_custom_role` — Купить право на кастомную роль (требуется название и цвет HEX)",
            inline=False
        )
        
        embed.add_field(
            name="🎮 Настройка и Управление",
            value="`/menu` — Вызвать меню настройки ролей (игры и программирование)\n"
                  "`/update_roles` — Принудительно обновить доступы к приватным каналам",
            inline=False
        )
        
        embed.set_footer(text="Все команды также работают через префикс '!', например !play")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CustomHelp(bot))
