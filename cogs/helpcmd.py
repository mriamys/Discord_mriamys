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
                  "`/stop` — Очистить очередь и выйти",
            inline=False
        )
        
        embed.add_field(
            name="💎 Экономика и Ранги",
            value="`/profile` — Твой профиль (уровень, коины, часы в войсе)\n"
                  "`/shop` — Посмотреть свой баланс для магазина\n"
                  "*(Магазин рофлов и ролей доступен в специальном канале магазина через кнопки)*",
            inline=False
        )
        
        embed.add_field(
            name="🎮 Настройка и Управление (Для всех)",
            value="Пользовательские команды:\n"
                  "`/update_roles` — Сохраняет твои роли и синхронизирует чаты\n"
                  "*(Меню выбора ролей и языков находится в канале выдачи ролей)*",
            inline=False
        )

        embed.add_field(
            name="🔒 Админские команды",
            value="`!menu` — Заспавнить интерактивное меню ролей\n"
                  "`!setup_shop` — Заспавнить интерактивный магазин\n"
                  "`!setup_dynamic_voice` — Настроить категорию для Авто-Приваток\n"
                  "`!add_coins <user> <amount>` — Выдать VibeКоины",
            inline=False
        )
        
        embed.set_footer(text="Mriamys Bot | Создано при поддержке Antigravity")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CustomHelp(bot))
