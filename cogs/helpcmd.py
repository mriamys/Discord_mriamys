import discord
from discord.ext import commands
from config import COLOR_MAIN


class CustomHelp(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="help",
        aliases=["команды", "помощь"],
        description="Показать список всех команд бота",
    )
    async def help_command(self, ctx):
        is_wrong_channel = False
        rank_channel = discord.utils.get(ctx.guild.text_channels, name="📜┃ранг")
        if rank_channel and ctx.channel.id != rank_channel.id:
            is_wrong_channel = True

        if is_wrong_channel:
            if ctx.interaction:
                await ctx.interaction.response.send_message(
                    f"Перейди в канал {rank_channel.mention}, помощь отправлена туда!",
                    ephemeral=True,
                )
            else:
                try:
                    await ctx.message.delete()
                except Exception:
                    pass
                msg = await ctx.send(
                    f"{ctx.author.mention}, список команд отправлен в {rank_channel.mention}!"
                )
                try:
                    import asyncio

                    self.bot.loop.create_task(msg.delete(delay=10))
                except Exception:
                    pass
        else:
            if ctx.interaction:
                await ctx.defer()

        embed = discord.Embed(
            title="🌌 Путеводитель по Mriamys",
            description="Добро пожаловать! Ниже представлен функционал бота. Большинство команд поддерживают как слэш `/команда`, так и префикс `!команда`.",
            color=COLOR_MAIN,
        )
        embed.set_thumbnail(
            url=self.bot.user.display_avatar.url if self.bot.user.avatar else None
        )

        embed.add_field(
            name="🎵 Музыка",
            value="`/play <запрос/url>` — Включить трек\n"
            "`/skip` — Пропустить трек\n"
            "`/pause` / `/resume` — Пауза и продолжение\n"
            "`/queue` — Показать очередь\n"
            "`/stop` — Очистить очередь и выгнать бота",
            inline=False,
        )

        embed.add_field(
            name="💎 Статистика и Экономика",
            value="`/profile` — Твоя карточка профиля (уровень, опыт, коины)\n"
            "`/stat` — Подробная текстовая статистика\n"
            "`/top` — Посмотреть списки лидеров сервера\n"
            "`/баланс` — Узнать свой текущий баланс VibeКоинов",
            inline=False,
        )

        embed.add_field(
            name="🎲 Развлечения и Магазин",
            value="Все игры (Казино, Кейсы, Дуэли) и покупки привилегий (Мемы, Бусты, Роли) доступны **через удобные кнопки в специальном канале магазина**.\n"
            "Отдельных команд для них вводить не нужно!",
            inline=False,
        )
        embed.set_footer(text="Mriamys Bot")
        
        if is_wrong_channel:
            await rank_channel.send(content=ctx.author.mention, embed=embed)
        else:
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CustomHelp(bot))
