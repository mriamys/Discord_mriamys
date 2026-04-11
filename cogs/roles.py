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
    "Программист": "💻",
    "Python": "🐍",
    "JavaScript": "📜",
    "TypeScript": "📘",
    "Java": "☕",
    "C++": "⚙️",
    "C#": "💠",
    "C": "🔧",
    "Go": "🐹",
    "Rust": "🦀",
    "PHP": "🐘",
    "Ruby": "💎",
    "Swift": "🍎",
    "Kotlin": "🤖",
    "HTML": "🌐",
    "CSS": "🎨",
    "SQL": "💾",
    "Bash": "🐧"
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
        await interaction.response.defer(ephemeral=True)
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
                role = await guild.create_role(name=game, mentionable=True, hoist=True, color=discord.Color.random())
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
                
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False, connect=False),
                    role: discord.PermissionOverwrite(read_messages=True, connect=True)
                }
                
                try:
                    category = await guild.create_category(cat_name, overwrites=overwrites)
                    # Создаем дефолтные каналы в ней
                    await guild.create_text_channel(f"💬┃{game.lower()}-chat", category=category)
                    await guild.create_voice_channel(f"🔊┃{game.upper()}", category=category)
                except Exception as e:
                    print(f"Не удалось создать каналы игры {game}: {e}")
            else:
                # На всякий случай обновляем права для категории, чтобы скрыть ее от всех, кроме тех, у кого роль
                try:
                    await category.set_permissions(role, read_messages=True, connect=True)
                    await category.set_permissions(guild.default_role, read_messages=False, connect=False)
                except Exception as e:
                    print(f"Не удалось обновить права для {game}: {e}")

        await interaction.followup.send("Ваши игровые роли успешно обновлены! (Были добавлены нужные чаты, если их не было)", ephemeral=True)


class DevSelect(discord.ui.Select):
    def __init__(self):
        options = []
        for dev, emoji in DEV_OPTIONS.items():
            desc = "Основная роль" if dev == "Программист" else f"Кодер на {dev}"
            options.append(discord.SelectOption(label=dev, emoji=emoji, description=desc))
            
        super().__init__(
            placeholder="Выберите языки программирования...",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id="select_dev_roles"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = interaction.user
        
        selected_devs = self.values
        
        # Роль программиста (общая)
        base_prog_role = discord.utils.get(guild.roles, name="Программист")
        
        # Удаляем роли
        for dev in DEV_OPTIONS.keys():
            role_name = "Программист" if dev == "Программист" else f"{dev} Coder"
            if dev not in selected_devs:
                role = discord.utils.get(guild.roles, name=role_name)
                if role and role in member.roles:
                    await member.remove_roles(role)

        # Выдаем и создаем каналы
        for dev in selected_devs:
            role_name = "Программист" if dev == "Программист" else f"{dev} Coder"
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                role = await guild.create_role(name=role_name, mentionable=True, hoist=True, color=discord.Color.from_rgb(46, 204, 113))
            if role not in member.roles:
                await member.add_roles(role)
                
        # Если была выбрана хотя бы одна галочка (любой ЯП или сам "Программист"), даем базовую роль "Программист"
        if selected_devs:
            if not base_prog_role:
                base_prog_role = await guild.create_role(name="Программист", mentionable=True, hoist=True, color=discord.Color.from_rgb(46, 204, 113))
            if base_prog_role not in member.roles:
                await member.add_roles(base_prog_role)
                
        # Ищем категорию
        cat_name = "💻┃ПРОГРАММИРОВАНИЕ"
        category = discord.utils.get(guild.categories, name=cat_name)
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False, connect=False)
            }
            try:
                category = await guild.create_category(cat_name, overwrites=overwrites)
                await guild.create_voice_channel("🎙️┃ОБЩИЙ ВОЙС IT", category=category)
            except Exception as e:
                print(e)
                
        if category:
            # Разрешаем всем выбранным ролям видеть эту категорию
            try:
                # Даем доступ всем кодерам + базовому "Программист"
                if selected_devs and base_prog_role:
                    await category.set_permissions(base_prog_role, read_messages=True, connect=True)
                for dev in selected_devs:
                    role_name = "Программист" if dev == "Программист" else f"{dev} Coder"
                    role = discord.utils.get(guild.roles, name=role_name)
                    if role:
                        await category.set_permissions(role, read_messages=True, connect=True)
            except Exception:
                pass
            # Создаем текстовые чаты для каждого выбранного направления
            for dev in selected_devs:
                if dev == "Программист":
                    continue # Для общей роли мы не создаем отдельный чат
                    
                role_name = f"{dev} Coder"
                role = discord.utils.get(guild.roles, name=role_name)
                
                clean_name = dev.lower().replace("++", "pp").replace("#", "sharp")
                chan_name = f"💬┃{clean_name}-chat"
                existing_channel = discord.utils.get(guild.text_channels, name=chan_name)
                
                chan_overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    role: discord.PermissionOverwrite(read_messages=True)
                }
                
                if category and not existing_channel:
                    try:
                        await guild.create_text_channel(chan_name, category=category, overwrites=chan_overwrites)
                    except Exception as e:
                        print(e)
                elif existing_channel:
                    try:
                        await existing_channel.set_permissions(role, read_messages=True)
                        await existing_channel.set_permissions(guild.default_role, read_messages=False)
                    except Exception:
                        pass

        await interaction.followup.send("Ваши роли программиста обновлены!", ephemeral=True)


class GameRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(GameSelect())


class DevRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DevSelect())


class RolesCog(commands.Cog):
    """Система интерактивной выдачи ролей"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setup_roles")
    @commands.has_permissions(administrator=True)
    async def setup_roles(self, ctx):
        await ctx.message.delete()
        
        # --- EMBED ДЛЯ ИГР ---
        game_embed = discord.Embed(
            title="🎮 ВЫБОР ИГРОВЫХ РОЛЕЙ",
            description=">>> Выбирай игры из списка ниже, чтобы мы знали, во что ты катаешь!\n✅ **Авто-доступ:** Откроются скрытые каналы игр.\n🌐 Если каналов для твоей игры еще нет, бот создаст их сам!",
            color=0xff4757
        )
        game_embed.set_image(url="https://i.pinimg.com/originals/a6/90/13/a690132b904eb12cccf80e927c7cfbc2.gif") # Красивая игровая гифка
        
        await ctx.send(embed=game_embed, view=GameRoleView())
        
        # --- EMBED ДЛЯ КОДЕРОВ ---
        dev_embed = discord.Embed(
            title="💻 НАВЫКИ ПРОГРАММИРОВАНИЯ",
            description=">>> Ты из VibeCoding? Укажи языки программирования, на которых пишешь!\n🔥 Покажи всем, что ты Senior-разработчик сервера.",
            color=0x2ed573
        )
        dev_embed.set_image(url="https://i.pinimg.com/originals/f3/9d/23/f39d2319bf30c4f8280695ee91b945ba.gif") # Хакерская/Кодерская гифка
        
        await ctx.send(embed=dev_embed, view=DevRoleView())

async def setup(bot):
    await bot.add_cog(RolesCog(bot))
    # Регистрируем Views как persistent для сохранения работы после перезапуска
    bot.add_view(GameRoleView())
    bot.add_view(DevRoleView())
