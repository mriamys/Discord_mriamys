import discord
from discord.ext import commands
from config import COLOR_MAIN

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="adminhelp", description="[Admin] Показать список всех административных команд")
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

        embed.set_footer(text=f"Запросил: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))
