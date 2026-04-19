import discord
from discord.ext import commands
from discord import app_commands
from config import COLOR_MAIN

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="adminhelp", description="[Admin] Показать список всех административных команд")
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def adminhelp(self, ctx):
        embed = discord.Embed(
            title="🛠 ПАНЕЛЬ АДМИНИСТРАТОРА",
            description="Ниже приведен полный список команд для настройки и управления сервером.\nВсе команды поддерживают `/` и `!`.",
            color=COLOR_MAIN
        )
        
        embed.add_field(
            name="💰 Экономика и Магазин",
            value="`/give-money <user> <amount>` — Выдать VibeКоины (Owner only).\n"
                  "`/setup_shop` — Инициализировать канал магазина.\n"
                  "`/clear_threads` — Удалить все игровые комнаты (ветки) в канале.",
            inline=False
        )
        
        embed.add_field(
            name="🎲 Игровые Панели",
            value="`/казик` — Создать панель управления Казино.\n"
                  "`/bj_setup` — Создать панель управления Блэкджеком.",
            inline=False
        )
        
        embed.add_field(
            name="🎭 Роли и Голос",
            value="`/setup_roles` — Создать панель выбора ролей (Игры/IT).\n"
                  "`/setup_dynamic_voice` — Настроить систему динамических приваток.",
            inline=False
        )

        # Безопасное получение аватарки
        avatar_url = ctx.author.display_avatar.url if ctx.author.avatar else None
        embed.set_footer(text=f"Администратор: {ctx.author.display_name}", icon_url=avatar_url)

        await ctx.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))
