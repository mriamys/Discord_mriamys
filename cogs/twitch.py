import discord
from discord.ext import commands, tasks
import aiohttp
import os
import logging
from config import COLOR_SUCCESS

class TwitchNotifier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client_id = os.getenv("TWITCH_CLIENT_ID")
        self.client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        self.twitch_channel = os.getenv("TWITCH_CHANNEL", "mriamys")
        self.announce_channel_id = os.getenv("TWITCH_ANNOUNCE_CHANNEL_ID")
        
        self.is_live = False
        self.app_access_token = None
        
        if self.client_id and self.client_secret:
            logging.info(f"TwitchNotifier enabled for channel: {self.twitch_channel}")
            self.check_twitch.start()
        else:
            logging.warning("TwitchNotifier is disabled because TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET is not set in .env")
            
    def cog_unload(self):
        self.check_twitch.cancel()

    async def get_access_token(self):
        url = f"https://id.twitch.tv/oauth2/token?client_id={self.client_id}&client_secret={self.client_secret}&grant_type=client_credentials"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.app_access_token = data.get("access_token")
                        return True
                    else:
                        logging.error(f"Failed to get Twitch access token: HTTP {response.status}")
        except Exception as e:
            logging.error(f"Error getting Twitch access token: {e}")
        return False
        
    @tasks.loop(minutes=2)
    async def check_twitch(self):
        if not self.app_access_token:
            success = await self.get_access_token()
            if not success:
                return
                
        url = f"https://api.twitch.tv/helix/streams?user_login={self.twitch_channel}"
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.app_access_token}"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 401: # Token expired
                        logging.warning("Twitch token expired, refreshing...")
                        self.app_access_token = None
                        return
                        
                    if response.status == 200:
                        data = await response.json()
                        streams = data.get("data", [])
                        is_currently_live = len(streams) > 0
                        
                        if is_currently_live and not self.is_live:
                            self.is_live = True
                            stream_info = streams[0]
                            logging.info(f"Twitch channel {self.twitch_channel} just went LIVE!")
                            await self.announce_stream(stream_info)
                        elif not is_currently_live and self.is_live:
                            self.is_live = False
                            logging.info(f"Twitch channel {self.twitch_channel} went offline.")
                    else:
                        logging.error(f"Twitch API returned HTTP {response.status}")
        except Exception as e:
            logging.error(f"Error checking Twitch status: {e}")

    @check_twitch.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def announce_stream(self, stream_info):
        title = stream_info.get("title", "Трансляция началась!")
        game = stream_info.get("game_name", "Just Chatting")
        viewer_count = stream_info.get("viewer_count", 0)
        
        # Replace {width} and {height} placeholders in thumbnail URL
        thumbnail_url = stream_info.get("thumbnail_url", "").replace("{width}", "1280").replace("{height}", "720")
        
        embed = discord.Embed(
            title=f"🔴 {self.twitch_channel} только что запустил стрим на Twitch!",
            description=f"**{title}**\n\n🎮 Категория: **{game}**\n👥 Зрителей прямо сейчас: **{viewer_count}**\n\n👉 **[Присоединяйся к просмотру!]({f'https://www.twitch.tv/{self.twitch_channel}'})**",
            url=f"https://www.twitch.tv/{self.twitch_channel}",
            color=0x9146FF # Twitch purple brand color
        )
        
        if thumbnail_url:
            # Cache bust to get latest thumbnail
            embed.set_image(url=f"{thumbnail_url}?t={int(discord.utils.utcnow().timestamp())}")
            
        embed.set_thumbnail(url="https://w7.pngwing.com/pngs/399/867/png-transparent-twitch-logo-streaming-media-twitch-logo-miscellaneous-purple-text-thumbnail.png")

        channel = None
        # Try finding the configured channel by ID
        if self.announce_channel_id and self.announce_channel_id.isdigit():
            channel = self.bot.get_channel(int(self.announce_channel_id))
            
        if not channel:
            # Fallback algorithm if channel not set or not found
            for guild in self.bot.guilds:
                # 1. Try system channel
                channel = guild.system_channel
                # 2. Try looking for 'уведомления' or 'стримы' or 'основной'
                if not channel:
                    for text_channel in guild.text_channels:
                        name = text_channel.name.lower()
                        if any(x in name for x in ['уведомления', 'стримы', 'основной']):
                            if text_channel.permissions_for(guild.me).send_messages:
                                channel = text_channel
                                break
                # 3. Just send to the first channel we have permission
                if not channel:
                    channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
                
                if channel:
                    await channel.send(content="@everyone 📢 Новый стрим!", embed=embed)
        else:
            await channel.send(content="@everyone 📢 Новый стрим!", embed=embed)

async def setup(bot):
    await bot.add_cog(TwitchNotifier(bot))
