import discord
from discord.ext import commands

# Словари эмодзи для красоты
GAME_OPTIONS = {
    "CS2": "🎯",
    "Rust": "🏕️",
    "Valorant": "🎭",
    "Apex Legends": "🔫",
    "Fortnite": "⛏️",
    "GTA V": "💰",
    "GTA SA": "🚗",
    "Rocket League": "🏎️",
    "Among Us": "🔪",
    "Euro Truck": "🚛",
    "Dota 2": "⚔️",
    "Minecraft": "🪚",
    "League of Legends": "🧙‍♂️",
    "PUBG": "🍳"
}

DEV_OPTIONS = {
    "Python": "🐍",
    "Java": "☕",
    "JavaScript": "📜",
    "CSS": "🎨",
    "HTML": "🌐",
    "C++": "⚙️",
    "C#": "💠"
}


class GameSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=game, emoji=emoji, description=f"Роль игрока {game}")
            for game, emoji in GAME_OPTIONS.items()
        ]
        super().__init__(
            placeholder="Выберите игры (можно несколько)...",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id="select_game_roles"
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        
        selected_games = self.values
        # Удаляем все игровые роли, которые юзер снял
        for game in GAME_OPTIONS.keys():
            if game not in selected_games:
                role = discord.utils.get(guild.roles, name=game)
                if role and role in member.roles:
                    await member.remove_roles(role)

        # Выдаем роли, которые юзер выбрал
        added = []
        for game in selected_games:
            role = discord.utils.get(guild.roles, name=game)
            if not role:
                role = await guild.create_role(name=game, mentionable=True, color=discord.Color.random())
            if role not in member.roles:
                await member.add_roles(role)
                added.append(game)
                
            # Проверки и создания категорий
            # Ищем, есть ли уже категория с таким именем (содержит имя)
            category = None
            for cat in guild.categories:
                if game.upper() in cat.name.upper():
                    category = cat
                    break
            
            if not category:
                # Создаем новую категорию
                emoji = GAME_OPTIONS.get(game, "🎮")
                cat_name = f"{emoji}┃{game.upper()}"
                try:
                    category = await guild.create_category(cat_name)
                    # Создаем дефолтные каналы в ней
                    await guild.create_text_channel(f"💬┃{game.lower()}-chat", category=category)
                    await guild.create_voice_channel(f"🔊┃{game.upper()}", category=category)
                except Exception as e:
                    print(f"Не удалось создать каналы игры {game}: {e}")

        await interaction.response.send_message("Ваши игровые роли успешно обновлены! (Были добавлены нужные чаты, если их не было)", ephemeral=True)


class DevSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=dev, emoji=emoji, description=f"Я кодер на {dev}")
            for dev, emoji in DEV_OPTIONS.items()
        ]
        super().__init__(
            placeholder="Выберите языки программирования...",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id="select_dev_roles"
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        
        selected_devs = self.values
        # Удаляем роли
        for dev in DEV_OPTIONS.keys():
            role_name = f"{dev} Coder"
            if dev not in selected_devs:
                role = discord.utils.get(guild.roles, name=role_name)
                if role and role in member.roles:
                    await member.remove_roles(role)

        # Выдаем
        for dev in selected_devs:
            role_name = f"{dev} Coder"
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                role = await guild.create_role(name=role_name, mentionable=True, color=discord.Color.from_rgb(46, 204, 113))
            if role not in member.roles:
                await member.add_roles(role)

        await interaction.response.send_message("Ваши роли программиста обновлены!", ephemeral=True)


class RoleSelectionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(GameSelect())
        self.add_item(DevSelect())


class RolesCog(commands.Cog):
    """Система интерактивной выдачи ролей"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setup_roles")
    @commands.has_permissions(administrator=True)
    async def setup_roles(self, ctx):
        embed = discord.Embed(
            title="🎭 ВЫДАЧА РОЛЕЙ",
            description="Выберите игры, в которые вы играете, чтобы открыть доступ к их скрытым каналам!\nТакже можете указать языки программирования, на которых пишете.",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_image(url="https://media.discordapp.net/attachments/1118193026362097725/1155160867455701142/line.gif") # Декоративная линия
        
        await ctx.send(embed=embed, view=RoleSelectionView())
        await ctx.message.delete()

async def setup(bot):
    await bot.add_cog(RolesCog(bot))
    # Регистрируем View как persistent для сохранения работы после перезапуска
    bot.add_view(RoleSelectionView())
