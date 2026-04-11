import discord
from discord.ext import commands
import math
import logging
from config import COLOR_SUCCESS
from utils.db import db
import os
import sqlite3 # Not used natively but maybe later

# Уровни и названия ролей (каждые 5 уровней)
MEME_RANKS = {
    0: "[🌫️] Кринж",
    5: "[👞] Попуск",
    10: "[👶] Шкет",
    15: "[🍺] Подпивас",
    20: "[🧔] Скуф",
    25: "[🧘] На чилле",
    30: "[🕺] Флексер",
    35: "[🕶️] Нормис",
    40: "[🔥] Тот самый",
    45: "[👌] Мегахорош",
    50: "[🗿] Гигачад",
    55: "[⚡] Сигма",
    60: "[🧚] Альтушка",
    65: "[👵] Олд",
    70: "[🌟] Легенда",
    75: "[🧔‍♂️] Гранд-Скуф",
    80: "[👑] Папич",
    90: "[🏋️] Босс качалки",
    100: "[🌌] Абсолют"
}

class LevelUpView(discord.ui.View):
    def __init__(self, member=None):
        super().__init__(timeout=None)
        self.member = member

    @discord.ui.button(label="Мой профиль 👤", style=discord.ButtonStyle.primary, custom_id="levelup_profile")
    async def show_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Только тот, кто аппнул уровень, может смотреть быстро свой (или любой может смотреть свой, но передаем member)
        await interaction.response.defer(ephemeral=True)
        user_data = await db.get_user(str(interaction.user.id))
        level = user_data.get('level', 0)
        xp = user_data.get('xp', 0)
        vibecoins = user_data.get('vibecoins', 0)
        voice_seconds = user_data.get('voice_time_seconds', 0)
        
        # Добавляем текущую сессию войса в реальном времени, если он сейчас сидит
        import time
        economy_cog = interaction.client.get_cog("Economy")
        if economy_cog and str(interaction.user.id) in economy_cog.voice_sessions:
            current_session = int(time.time() - economy_cog.voice_sessions[str(interaction.user.id)])
            voice_seconds += current_session
        
        # Получаем данные о кастомном фоне профиля (если есть)
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT bg_color FROM profile_settings WHERE user_id = %s", (str(interaction.user.id),))
                profile_settings = await cur.fetchone()
                
        bg_color = profile_settings.get("bg_color", "#2b2d31") if profile_settings else "#2b2d31"
        
        from utils.images import generate_profile_card
        import io
        
        # Для ранга нам нужен ког Leveling:
        cog = interaction.client.get_cog("Leveling")
        rank_name = cog.get_rank_role_name_for_level(level) if cog else "Unknown"
        
        user_achievements = await db.get_achievements(str(interaction.user.id))
        
        image_bytes = await generate_profile_card(interaction.user, level, xp, vibecoins, voice_seconds, rank_name, bg_color, user_achievements)
        
        if isinstance(image_bytes, bytes):
            fp = io.BytesIO(image_bytes)
        else:
            fp = image_bytes
            fp.seek(0)
            
        file = discord.File(fp=fp, filename="profile.png")
        await interaction.followup.send(file=file, ephemeral=True)

    @discord.ui.button(label="В Магазин 🛒", style=discord.ButtonStyle.secondary, custom_id="levelup_shop")
    async def go_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        shop_channel = discord.utils.get(interaction.guild.text_channels, name="🛒┃магазин")
        if not shop_channel:
            shop_channel = discord.utils.get(interaction.guild.text_channels, name="магазин")
            
        if shop_channel:
            msg = f"Загляни в канал {shop_channel.mention}, чтобы потратить свои VibeКоины!"
        else:
            msg = "Загляни в канал магазина, чтобы потратить свои VibeКоины!"
            
        await interaction.response.send_message(msg, ephemeral=True)


class ProfileView(discord.ui.View):
    def __init__(self, target_member: discord.Member):
        super().__init__(timeout=None)
        self.target_member = target_member

    @discord.ui.button(label="Трофеи 🏆", style=discord.ButtonStyle.primary, custom_id="profile_trophies")
    async def show_trophies(self, interaction: discord.Interaction, button: discord.ui.Button):
        from utils.achievements_data import ACHIEVEMENTS
        user_achievements = await db.get_achievements(str(self.target_member.id))
        
        if not user_achievements:
            await interaction.response.send_message(f"У {self.target_member.display_name} пока нет трофеев.", ephemeral=True)
            return
            
        RARITY_ORDER = {"legendary": 4, "epic": 3, "rare": 2, "common": 1}
        sorted_ach = sorted(
            user_achievements,
            key=lambda x: RARITY_ORDER.get(ACHIEVEMENTS.get(x, {}).get("rarity", "common"), 0),
            reverse=True
        )
        
        embed = discord.Embed(
            title=f"🏆 Трофеи: {self.target_member.display_name}",
            color=0xF1C40F
        )
        
        desc = ""
        rarity_icons = {"common": "⚪ Обычная", "rare": "🔵 Редкая", "epic": "🟣 Эпическая", "legendary": "🟡 Легендарная"}
        for ach_id in sorted_ach:
            if ach_id in ACHIEVEMENTS:
                ach = ACHIEVEMENTS[ach_id]
                r_icon = rarity_icons.get(ach.get("rarity", "common"), "⚪ Обычная")
                desc += f"{ach['emoji']} **{ach['name']}** ({r_icon})\n_{ach['desc']}_\n\n"
                
        embed.description = desc
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="В Магазин 🛒", style=discord.ButtonStyle.secondary, custom_id="profile_shop")
    async def go_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        shop_channel = discord.utils.get(interaction.guild.text_channels, name="🛒┃магазин")
        if not shop_channel:
            shop_channel = discord.utils.get(interaction.guild.text_channels, name="магазин")
            
        if shop_channel:
            msg = f"Загляни в канал {shop_channel.mention}, чтобы потратить свои VibeКоины!"
        else:
            msg = "Загляни в канал магазина, чтобы потратить свои VibeКоины!"
            
        await interaction.response.send_message(msg, ephemeral=True)


class TopView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=120)
        self.author = author

    @discord.ui.select(
        placeholder="Выберите категорию...",
        options=[
            discord.SelectOption(label="🏆 Уровень (XP)", value="level", description="Самые прокачанные пользователи"),
            discord.SelectOption(label="💰 VibeКоины", value="coins", description="Самые богатые пользователи"),
            discord.SelectOption(label="🎙️ Голосовой актив", value="voice", description="Больше всего времени в войсах"),
            discord.SelectOption(label="🔥 Стрики", value="streak", description="Самые длинные серии общения"),
        ]
    )
    async def select_category(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Это меню не для вас!", ephemeral=True)
            return
            
        category = select.values[0]
        await interaction.response.defer()
        
        from utils.db import db
        data = await db.get_leaderboard(category, limit=10)
        
        titles = {
            "level": "🏆 ТОП-10 по Уровню",
            "coins": "💰 ТОП-10 по Коинам",
            "voice": "🎙️ ТОП-10 по Голосу",
            "streak": "🔥 ТОП-10 по Стрикам"
        }
        
        embed = discord.Embed(title=titles[category], color=0x2b2d31)
        
        if not data:
            embed.description = "Пусто..."
        else:
            desc = ""
            for idx, user_data in enumerate(data, 1):
                member = interaction.guild.get_member(int(user_data['user_id']))
                name = member.mention if member else f"<@{user_data['user_id']}>"
                
                medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
                
                if category == "level":
                    val = f"Ур. {user_data['level']} ({user_data['xp']} XP)"
                elif category == "coins":
                    val = f"{user_data['vibecoins']} VC"
                elif category == "voice":
                    s = user_data.get('voice_time_seconds', 0)
                    val = f"{s // 3600}ч {(s % 3600) // 60}м"
                elif category == "streak":
                    val = f"{user_data['streak']} 🔥"
                    
                desc += f"{medal} {name} — **{val}**\n"
                
            embed.description = desc
            
        await interaction.message.edit(embed=embed, view=self)

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="top", aliases=["топ"], description="Посмотреть списки лидеров сервера")
    async def top(self, ctx):
        if ctx.guild is None:
            await ctx.send("Эта команда доступна только на сервере!")
            return
            
        from utils.db import db
        data = await db.get_leaderboard("level", limit=10)
        embed = discord.Embed(title="🏆 ТОП-10 по Уровню", color=0x2b2d31)
        
        if not data:
            embed.description = "Пусто..."
        else:
            desc = ""
            for idx, user_data in enumerate(data, 1):
                member = ctx.guild.get_member(int(user_data['user_id']))
                name = member.mention if member else f"<@{user_data['user_id']}>"
                medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
                val = f"Ур. {user_data['level']} ({user_data['xp']} XP)"
                desc += f"{medal} {name} — **{val}**\n"
            embed.description = desc
            
        view = TopView(ctx.author)
        await ctx.send(embed=embed, view=view)


    def calc_level(self, xp):
        # Формула: XP = (Уровень / 0.023) ^ 2
        # Уровень = 0.023 * sqrt(XP)
        return int(0.023 * math.sqrt(xp))
        
    def get_rank_role_name_for_level(self, level):
        highest_rank = MEME_RANKS[0]
        for lvl in sorted(MEME_RANKS.keys()):
            if level >= lvl:
                highest_rank = MEME_RANKS[lvl]
            else:
                break
        return highest_rank

    @commands.Cog.listener()
    async def on_xp_updated(self, member, new_xp):
        # Преобразуем User в Member, если пришёл User (например, из фоновой задачи Economy)
        if not hasattr(member, 'guild'):
            for guild in self.bot.guilds:
                m = guild.get_member(member.id)
                if m:
                    member = m
                    break
                    
        # Если гильдия так и не найдена (пользователь ливнул или это DM без гильдии)
        if not hasattr(member, 'guild'):
            return

        # Событие вызывается из Economy, когда начисляется XP
        user_data = await db.get_user(str(member.id))
        old_level = user_data.get('level', 0)
        new_level = self.calc_level(new_xp)
        
        # Обновляем уровень в базе если он вырос
        if new_level > old_level:
            await db.update_user(str(member.id), level=new_level)
            
        # Всегда синхронизируем роль, даже если левел не апнулся 
        # (чтобы выдавать роль "Кринж" самым новым игрокам)
        target_role_name = self.get_rank_role_name_for_level(new_level)
        role = discord.utils.get(member.guild.roles, name=target_role_name)
        
        if role and role not in member.roles:
            # Удаляем старые ранговые роли
            rank_names = list(MEME_RANKS.values())
            roles_to_remove = [r for r in member.roles if r.name in rank_names]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove)
                
            await member.add_roles(role)
            
            # Уведомляем игрока о повышении ТОЛЬКО если уровень реально вырос
            if new_level > old_level:
                embed = discord.Embed(
                    title="🎉 НОВЫЙ РАНГ!",
                    description=f"Ты получил **{new_level}** уровень и стал **{target_role_name}**!",
                    color=COLOR_SUCCESS
                )
                
                rank_channel = discord.utils.get(member.guild.text_channels, name="📜┃ранг")
                view = LevelUpView(member)
                try:
                    if rank_channel:
                        await rank_channel.send(content=f"{member.mention}", embed=embed, view=view)
                    else:
                        await member.send(embed=embed, view=view)
                except Exception as e:
                    logging.error(f"Could not setup rank msg: {e}")
            elif new_level == 0:
                # Оповещение о самом первом ранге (Кринж)
                embed = discord.Embed(
                    title="🌫️ НАЧАЛО ПУТИ!",
                    description=f"Твой опыт начал копиться, и ты получаешь свой первый ранг — **{target_role_name}**!\nПродолжай активно общаться, чтобы повышать его!",
                    color=0x808080
                )
                
                rank_channel = discord.utils.get(member.guild.text_channels, name="📜┃ранг")
                view = LevelUpView(member)
                try:
                    if rank_channel:
                        await rank_channel.send(content=f"{member.mention}", embed=embed, view=view)
                    else:
                        await member.send(embed=embed, view=view)
                except Exception as e:
                    logging.error(f"Could not setup rank msg: {e}")

    @commands.hybrid_command(name="profile", aliases=["ранг", "rank"], description="Показать твою или чужую карточку профиля")
    async def profile(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user_data = await db.get_user(str(member.id))
        
        level = user_data.get('level', 0)
        xp = user_data.get('xp', 0)
        vibecoins = user_data.get('vibecoins', 0)
        voice_seconds = user_data.get('voice_time_seconds', 0)
        
        import time
        economy_cog = self.bot.get_cog("Economy")
        if economy_cog and str(member.id) in economy_cog.voice_sessions:
            now = time.time()
            join_time = economy_cog.voice_sessions[str(member.id)]
            duration = int(now - join_time)
            
            if duration > 0:
                old_seconds = voice_seconds
                total_voice_time = old_seconds + duration
                
                old_minutes = old_seconds // 60
                new_minutes = total_voice_time // 60
                delta_minutes = new_minutes - old_minutes
                
                # Обновляем локальные переменные для отображения на картинке
                vibecoins += (delta_minutes * 2)
                xp += (delta_minutes * 10)
                voice_seconds = total_voice_time
                
                # Обновляем данные пользователя в БД в реальном времени
                await db.update_user(str(member.id), 
                                     vibecoins=vibecoins, 
                                     xp=xp, 
                                     voice_time_seconds=total_voice_time)
                                     
                if delta_minutes > 0:
                    self.bot.dispatch("xp_updated", member, xp)
                self.bot.dispatch("voice_time_updated", member, total_voice_time)
                
                # Сбрасываем сессию на сейчас, чтобы избежать двойного начисления
                economy_cog.voice_sessions[str(member.id)] = now
        
        rank_name = self.get_rank_role_name_for_level(level)
        
        # Автоматическая выдача роли ранга, если её нет (например, для новых юзеров с 0 уровнем)
        target_role = discord.utils.get(member.guild.roles, name=rank_name)
        if target_role and target_role not in member.roles:
            try:
                # Удаляем старые ранговые роли перед выдачей новой
                rank_names = list(MEME_RANKS.values())
                roles_to_remove = [r for r in member.roles if r.name in rank_names]
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove)
                await member.add_roles(target_role)
            except discord.Forbidden:
                pass
        
        await ctx.defer() # Картинка может генерироваться пару секунд
        
        # Получаем данные о кастомном фоне профиля (если есть)
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT bg_color FROM profile_settings WHERE user_id = %s", (str(member.id),))
                profile_settings = await cur.fetchone()
                
        bg_color = profile_settings.get("bg_color", "#2b2d31") if profile_settings else "#2b2d31"
        user_achievements = await db.get_achievements(str(member.id))
        streak = user_data.get('streak', 0)
        
        from utils.images import generate_profile_card
        import io
        
        image_bytes = await generate_profile_card(member, level, xp, vibecoins, voice_seconds, rank_name, bg_color, user_achievements, streak)
        
        if isinstance(image_bytes, bytes):
            fp = io.BytesIO(image_bytes)
        else:
            fp = image_bytes
            fp.seek(0)
            
        file = discord.File(fp=fp, filename="profile.png")
        view = ProfileView(member)
        await ctx.send(file=file, view=view)

    @commands.hybrid_command(name="stat", aliases=["стат", "статистика", "stats"], description="Показать детальную текстовую статистику пользователя")
    async def stat(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        
        user_data = await db.get_user(str(member.id))
        achievements = await db.get_achievements(str(member.id))
        
        from utils.achievements_data import ACHIEVEMENTS
        total_ach = len(ACHIEVEMENTS)
        
        level = user_data.get('level', 0)
        xp = user_data.get('xp', 0)
        vibecoins = user_data.get('vibecoins', 0)
        voice_sec = user_data.get('voice_time_seconds', 0)
        msgs = user_data.get('msg_count', 0)
        spent = user_data.get('shop_spent', 0)
        nicks = user_data.get('nick_changes', 0)
        streak = user_data.get('streak', 0)
        
        hours = voice_sec // 3600
        mins = (voice_sec % 3600) // 60
        
        embed = discord.Embed(title=f"📊 Статистика: {member.display_name}", color=0x2b2d31)
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)
        else:
            embed.set_thumbnail(url=member.default_avatar.url)
        
        embed.add_field(name="🏆 Уровень / XP", value=f"Ур. {level} ({xp} XP)", inline=True)
        embed.add_field(name="💰 VibeКоины", value=f"{vibecoins}", inline=True)
        embed.add_field(name="🌟 Ачивки", value=f"{len(achievements)} / {total_ach}", inline=True)
        
        embed.add_field(name="🎙️ В голосе", value=f"{hours}ч {mins}м", inline=True)
        embed.add_field(name="💬 Сообщений", value=f"{msgs}", inline=True)
        embed.add_field(name="🔥 Стрик", value=f"{streak} дней", inline=True)
        
        embed.add_field(name="🛒 Траты в магазине", value=f"{spent} VC", inline=True)
        embed.add_field(name="🤡 Смен ников", value=f"{nicks}", inline=True)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Leveling(bot))

