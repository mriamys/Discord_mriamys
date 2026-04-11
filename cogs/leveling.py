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
        await interaction.response.send_message("Загляни в канал <#1152865917300731908> (или где установлен Магазин) чтобы потратить свои VibeКоины!", ephemeral=True)


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
        
        await ctx.defer() # Картинка может генерироваться пару секунд
        
        # Получаем данные о кастомном фоне профиля (если есть)
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT bg_color FROM profile_settings WHERE user_id = %s", (str(member.id),))
                profile_settings = await cur.fetchone()
                
        bg_color = profile_settings.get("bg_color", "#2b2d31") if profile_settings else "#2b2d31"
        user_achievements = await db.get_achievements(str(member.id))
        
        from utils.images import generate_profile_card
        import io
        
        image_bytes = await generate_profile_card(member, level, xp, vibecoins, voice_seconds, rank_name, bg_color, user_achievements)
        
        if isinstance(image_bytes, bytes):
            fp = io.BytesIO(image_bytes)
        else:
            fp = image_bytes
            fp.seek(0)
            
        file = discord.File(fp=fp, filename="profile.png")
        await ctx.send(file=file)

async def setup(bot):
    await bot.add_cog(Leveling(bot))

