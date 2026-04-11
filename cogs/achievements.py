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
        elif msg_count == 100:
            await self.grant_achievement(member, "msg_100")
        elif msg_count == 1000:
            await self.grant_achievement(member, "msg_1000")
        elif msg_count == 10000:
            await self.grant_achievement(member, "keyboard_rambo")
        elif msg_count == 50000:
            await self.grant_achievement(member, "msg_50000")

    @commands.Cog.listener()
    async def on_voice_time_updated(self, member, total_voice_time):
        if total_voice_time >= 3600:
            await self.grant_achievement(member, "voice_1h")
        if total_voice_time >= 18000:
            await self.grant_achievement(member, "chair_glued")
        if total_voice_time >= 36000:
            await self.grant_achievement(member, "voice_10h")
        if total_voice_time >= 180000:
            await self.grant_achievement(member, "voice_50h")

    @commands.Cog.listener()
    async def on_shop_purchased(self, member, item_id, shop_spent, nick_changes):
        if shop_spent >= 1000:
            await self.grant_achievement(member, "store_1000")
        if shop_spent >= 5000:
            await self.grant_achievement(member, "ludoman")
        if shop_spent >= 20000:
            await self.grant_achievement(member, "store_20000")
            
        if item_id == "shut_up":
            await self.grant_achievement(member, "cringe_prisoner")
            
        if nick_changes >= 10:
            await self.grant_achievement(member, "jester")
        if nick_changes >= 20:
            await self.grant_achievement(member, "tilting_player")

    @commands.Cog.listener()
    async def on_xp_updated(self, member, new_xp):
        # 10 lvl = 189,035 xp
        if new_xp >= 189035:
            await self.grant_achievement(member, "level_10")
        # 50 lvl = 4,725,897 xp
        if new_xp >= 4725897:
            await self.grant_achievement(member, "level_50")
        # 100 lvl = 18,903,591 xp
        if new_xp >= 18903591:
            await self.grant_achievement(member, "absolute")
            
        user_data = await db.get_user(str(member.id))
        vibecoins = user_data.get('vibecoins', 0)
        
        if vibecoins >= 10000:
            await self.grant_achievement(member, "businessman")
        if vibecoins >= 50000:
            await self.grant_achievement(member, "crypto_hamster")

    @commands.Cog.listener()
    async def on_streak_updated(self, member, new_streak):
        if new_streak >= 3:
            await self.grant_achievement(member, "streak_3")
        if new_streak >= 7:
            await self.grant_achievement(member, "no_lifer")
        if new_streak >= 14:
            await self.grant_achievement(member, "streak_14")
        if new_streak >= 30:
            await self.grant_achievement(member, "streak_30")

async def setup(bot):
    await bot.add_cog(Achievements(bot))
