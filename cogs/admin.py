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
            description="Список команд, доступных только пользователям с правами администратора.",
            color=COLOR_MAIN
        )
        
        embed.add_field(
            name="💰 Экономика",
            value="`/give-money <user> <amount>` — Выдать VibeКоины пользователю.",
            inline=False
        )
        
        embed.add_field(
            name="🎲 Игровые Панели",
            value="`!казик` — Создать панель управления Казино.\n"
                  "`!bj_setup` — Создать панель управления Блэкджеком.",
            inline=False
        )
        
        embed.add_field(
            name="🛒 Настройка Магазина и Ролей",
            value="`!setup_shop` — Инициализировать канал магазина.\n"
                  "`!setup_roles` — Инициализировать панель выбора ролей.",
            inline=False
        )
        
        embed.add_field(
            name="🔊 Голосовые Каналы",
            value="`!setup_dynamic_voice` — Настроить систему динамических приваток.",
            inline=False
        )

        # Безопасное получение аватарки
        avatar_url = ctx.author.display_avatar.url if ctx.author.avatar else None
        embed.set_footer(text=f"Запросил: {ctx.author.display_name}", icon_url=avatar_url)

        try:
            # Для слеш-команд будет ephemeral=True, для текстовых бот просто отправит embed
            await ctx.send(embed=embed, ephemeral=True)
        except discord.errors.HTTPException:
            # Fallback для текстовых каналов, если ephemeral не поддерживается
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Admin(bot))
