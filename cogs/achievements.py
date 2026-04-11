import discord
from discord.ext import commands
from utils.db import db
from utils.achievements_data import ACHIEVEMENTS
from config import COLOR_SUCCESS
import logging

class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def grant_achievement(self, member: discord.Member, achievement_id: str):
        if achievement_id not in ACHIEVEMENTS:
            return
            
        success = await db.add_achievement(str(member.id), achievement_id)
        if success:
            ach_data = ACHIEVEMENTS[achievement_id]
            # Отправка уведомления об ачивке
            rank_channel = discord.utils.get(member.guild.text_channels, name="📜┃ранг")
            embed = discord.Embed(
                title=f"🏆 ПОЛУЧЕНО ДОСТИЖЕНИЕ: {ach_data['name']}!",
                description=f"**{ach_data['desc']}**\n\nМожешь проверить свою коллекцию в `!profile`!",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=ach_data['icon_url'])
            
            try:
                if rank_channel:
                    await rank_channel.send(content=member.mention, embed=embed)
                else:
                    await member.send(embed=embed)
            except Exception as e:
                logging.error(f"Failed to send achievement msg: {e}")

    @commands.Cog.listener()
    async def on_message_sent(self, member, msg_count):
        if msg_count == 1:
            await self.grant_achievement(member, "first_msg")
        elif msg_count == 10000:
            await self.grant_achievement(member, "keyboard_rambo")

    @commands.Cog.listener()
    async def on_voice_time_updated(self, member, total_voice_time):
        # 5 часов = 18000 секунд
        if total_voice_time >= 18000:
            await self.grant_achievement(member, "chair_glued")

    @commands.Cog.listener()
    async def on_shop_purchased(self, member, item_id, shop_spent, nick_changes):
        if shop_spent >= 5000:
            await self.grant_achievement(member, "ludoman")
            
        if item_id == "shut_up":
            await self.grant_achievement(member, "cringe_prisoner")
            
        if nick_changes >= 10:
            await self.grant_achievement(member, "jester")

    @commands.Cog.listener()
    async def on_xp_updated(self, member, new_xp):
        # Проверяем "Абсолют" (100 лвл = 1000000 xp) и "Мамкин бизнесмен" (баланс)
        user_data = await db.get_user(str(member.id))
        
        # Absolute (100 lvl formula is 0.1 * sqrt(xp). 100 / 0.1 = 1000. 1000^2 = 1,000,000 xp)
        if new_xp >= 1000000:
            await self.grant_achievement(member, "absolute")
            
        vibecoins = user_data.get('vibecoins', 0)
        if vibecoins >= 10000:
            await self.grant_achievement(member, "businessman")

async def setup(bot):
    await bot.add_cog(Achievements(bot))
