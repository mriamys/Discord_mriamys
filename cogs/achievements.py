import discord
from discord.ext import commands
from utils.db import db
from utils.achievements_data import ACHIEVEMENTS
import logging

class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.msg_thresholds = {1: 'first_msg', 10: 'msg_10', 50: 'msg_50', 100: 'msg_100', 250: 'msg_250', 500: 'msg_500', 1000: 'msg_1000', 2500: 'msg_2500', 5000: 'msg_5000', 10000: 'keyboard_rambo', 20000: 'msg_20000', 50000: 'msg_50000', 100000: 'msg_100000', 250000: 'msg_250000', 500000: 'msg_500000', 1000000: 'msg_1000000'}
        self.voice_thresholds = {600: 'voice_10m', 3600: 'voice_1h', 18000: 'chair_glued', 36000: 'voice_10h', 86400: 'voice_24h', 180000: 'voice_50h', 241200: 'voice_67h', 360000: 'voice_100h', 900000: 'voice_250h', 1800000: 'voice_500h', 3600000: 'voice_1000h', 18000000: 'voice_5000h'}
        self.shop_thresholds = {100: 'store_100', 500: 'store_500', 1000: 'store_1000', 5000: 'shop_ludoman', 20000: 'store_20000', 50000: 'store_50000', 100000: 'store_100000', 500000: 'store_500000', 1000000: 'store_1000000'}
        self.casino_thresholds = {10000: 'casino_10k', 100000: 'casino_ludoman'}
        self.bal_thresholds = {10000: 'businessman', 50000: 'crypto_hamster', 100000: 'bal_100000', 500000: 'bal_500000', 1000000: 'bal_1000000'}
        self.nick_thresholds = {1: 'nick_1', 5: 'nick_5', 10: 'jester', 15: 'nick_15', 20: 'tilting_player', 50: 'nick_50', 100: 'nick_100'}
        self.streak_thresholds = {3: 'streak_3', 5: 'streak_5', 7: 'no_lifer', 10: 'streak_10', 14: 'streak_14', 21: 'streak_21', 30: 'streak_30', 50: 'streak_50', 69: 'streak_69', 100: 'streak_100', 365: 'streak_365'}
        self.level_thresholds = {1890: 'level_1', 47258: 'level_5', 189035: 'level_10', 756143: 'level_20', 1701323: 'level_30', 3024574: 'level_40', 4725897: 'level_50', 6805293: 'level_60', 8485822: 'level_67', 9000000: 'level_69', 10633270: 'level_75', 12098298: 'level_80', 15311909: 'level_90', 18527410: 'level_99', 18903591: 'absolute'}

    async def grant_achievement(self, member: discord.Member, achievement_id: str):
        if achievement_id not in ACHIEVEMENTS:
            return
            
        success = await db.add_achievement(str(member.id), achievement_id)
        if success:
            ach_data = ACHIEVEMENTS[achievement_id]
            rank_channel = discord.utils.get(member.guild.text_channels, name="📜┃ранг")
            embed = discord.Embed(
                title=f"🏆 ПОЛУЧЕНО ДОСТИЖЕНИЕ: {ach_data['name']}!",
                description=f"**{ach_data['desc']}**\n\nМожешь проверить свою коллекцию в `profile`!",
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
        # We need to check if they passed specific milestones exactly, or just hit >= threshold?
        # Typically the db counter goes 1 by 1.
        if msg_count in self.msg_thresholds:
            await self.grant_achievement(member, self.msg_thresholds[msg_count])

    @commands.Cog.listener()
    async def on_voice_time_updated(self, member, total_voice_time):
        # voice time might skip exact seconds if bulk updated.
        for threshold, ach_id in self.voice_thresholds.items():
            if total_voice_time >= threshold:
                await self.grant_achievement(member, ach_id)

    @commands.Cog.listener()
    async def on_shop_purchased(self, member, item_id, shop_spent, nick_changes):
        # shop_spent can skip amounts
        for threshold, ach_id in self.shop_thresholds.items():
            if shop_spent >= threshold:
                await self.grant_achievement(member, ach_id)
                
        # nick changes can skip if multiple bought, but usually goes 1 by 1.
        for threshold, ach_id in self.nick_thresholds.items():
            if nick_changes >= threshold:
                await self.grant_achievement(member, ach_id)
                
        if item_id == "shut_up":
            await self.grant_achievement(member, "cringe_prisoner")
        elif item_id == "fake_status":
            await self.grant_achievement(member, "fake_status")
        elif item_id == "bunker":
            await self.grant_achievement(member, "bunker")

    @commands.Cog.listener()
    async def on_xp_updated(self, member, new_xp):
        # xp skips thresholds easily
        for threshold, ach_id in self.level_thresholds.items():
            if new_xp >= threshold:
                await self.grant_achievement(member, ach_id)
            
        user_data = await db.get_user(str(member.id))
        vibecoins = user_data.get('vibecoins', 0)
        
        for threshold, ach_id in self.bal_thresholds.items():
            if vibecoins >= threshold:
                await self.grant_achievement(member, ach_id)

    @commands.Cog.listener()
    async def on_streak_updated(self, member, new_streak):
        if new_streak in self.streak_thresholds:
            await self.grant_achievement(member, self.streak_thresholds[new_streak])

    @commands.Cog.listener()
    async def on_casino_played(self, member, total_spent, total_wins, payout, bet):
        for threshold, ach_id in self.casino_thresholds.items():
            if total_spent >= threshold:
                await self.grant_achievement(member, ach_id)
                
        # Проверка на джекпот x50
        if bet >= 10 and payout >= bet * 50:
            await self.grant_achievement(member, "casino_jackpot")

    @commands.Cog.listener()
    async def on_voice_role_interaction(self, member, channel_members):
        role_keywords = {
            "девушка": "ach_woman",
            "тяночка": "ach_woman",
            "woman": "ach_woman",
            "женщина": "ach_woman",
            "скуф": "ach_skuf",
            "админ": "ach_admin",
            "создатель": "ach_admin",
            "admin": "ach_admin"
        }
        
        for m in channel_members:
            if m.id == member.id or m.bot:
                continue
                
            if hasattr(m, 'roles'):
                for role in m.roles:
                    role_name_lo = role.name.lower()
                    for kw, ach_id in role_keywords.items():
                        if kw in role_name_lo:
                            await self.grant_achievement(member, ach_id)

    @commands.Cog.listener()
    async def on_message_reply_interaction(self, member, replied_to_member):
        role_keywords = {
            "девушка": "ach_woman_reply",
            "тяночка": "ach_woman_reply",
            "женщина": "ach_woman_reply"
        }
        if hasattr(replied_to_member, 'roles'):
            for role in replied_to_member.roles:
                role_name_lo = role.name.lower()
                for kw, ach_id in role_keywords.items():
                    if kw in role_name_lo:
                        await self.grant_achievement(member, ach_id)

async def setup(bot):
    await bot.add_cog(Achievements(bot))
