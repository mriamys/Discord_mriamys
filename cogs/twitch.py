import discord
from discord.ext import commands, tasks
import aiohttp
import os
import json
import logging
from config import COLOR_SUCCESS

class TwitchNotifier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client_id = os.getenv("TWITCH_CLIENT_ID")
        self.client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        self.main_channel = os.getenv("TWITCH_CHANNEL", "mriamys").lower()
        self.friend_channels = ["findmeq", "fafikxs", "xloret"]
        self.announce_channel_id = os.getenv("TWITCH_ANNOUNCE_CHANNEL_ID")
        
        self.app_access_token = None
        
        # State structure:
        # {
        #   "mriamys": {"is_live": False, "messages": [{"c": 123, "m": 456}]},
        #   "findmeq": {"is_live": False, "messages": []},
        #   ...
        # }
        self.stream_states = {}
        for ch in [self.main_channel] + self.friend_channels:
            self.stream_states[ch] = {"is_live": False, "messages": []}
            
        self.state_file = "data/twitch_state.json"
        
        # Загружаем сохраненные данные, чтобы не спамить после перезапуска
        self.load_state()
        
        if self.client_id and self.client_secret:
            logging.info(f"TwitchNotifier enabled for channels: {[self.main_channel] + self.friend_channels}")
            self.check_twitch.start()
        else:
            logging.warning("TwitchNotifier is disabled because TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET is not set in .env")
            
    def cog_unload(self):
        self.check_twitch.cancel()

    def save_state(self):
        os.makedirs("data", exist_ok=True)
        # We save raw stream dictionary so it's JSON serializable
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.stream_states, f)
        except Exception as e:
            logging.error(f"Error saving twitch state: {e}")

    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    for ch, state in data.items():
                        if ch in self.stream_states:
                            self.stream_states[ch] = state
            except Exception as e:
                logging.error(f"Error loading twitch state: {e}")

    async def get_announce_messages(self, channel_login):
        state = self.stream_states.get(channel_login)
        if not state: return []
        
        msgs = []
        valid_records = []
        for info in state["messages"]:
            try:
                channel = self.bot.get_channel(info["c"])
                if channel:
                    msg = await channel.fetch_message(info["m"])
                    msgs.append(msg)
                    valid_records.append(info)
            except Exception:
                pass
                
        # Remove deleted messages from state
        state["messages"] = valid_records
        return msgs

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
                
        logins = [self.main_channel] + self.friend_channels
        query = "&".join([f"user_login={login}" for login in logins])
        url = f"https://api.twitch.tv/helix/streams?{query}"
        
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
                        live_users = {s["user_login"].lower(): s for s in streams}
                        
                        changed = False
                        
                        for login in logins:
                            state = self.stream_states[login]
                            is_currently_live = login in live_users
                            
                            if is_currently_live:
                                stream_info = live_users[login]
                                if not state["is_live"]:
                                    state["is_live"] = True
                                    changed = True
                                    logging.info(f"Twitch channel {login} just went LIVE!")
                                    await self.announce_stream(login, stream_info)
                                else:
                                    await self.update_stream(login, stream_info)
                            elif not is_currently_live and state["is_live"]:
                                state["is_live"] = False
                                changed = True
                                logging.info(f"Twitch channel {login} went offline.")
                                await self.end_stream(login)
                                
                        if changed:
                            self.save_state()
                    else:
                        logging.error(f"Twitch API returned HTTP {response.status}")
        except Exception as e:
            logging.error(f"Error checking Twitch status: {e}")

    @check_twitch.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    def build_embed(self, login, stream_info):
        title = stream_info.get("title", "Трансляция началась!")
        game = stream_info.get("game_name", "Just Chatting")
        viewer_count = stream_info.get("viewer_count", 0)
        
        thumbnail_url = stream_info.get("thumbnail_url", "").replace("{width}", "1280").replace("{height}", "720")
        
        if login == self.main_channel:
            embed_title = f"🔴 {login} онлайн на Twitch!"
        else:
            embed_title = f"🔴 Стрим друга: {login} онлайн!"
            
        embed = discord.Embed(
            title=embed_title,
            description=f"**{title}**\n\n🎮 Категория: **{game}**\n👥 Зрителей прямо сейчас: **{viewer_count}**\n\n👉 **[Присоединяйся к просмотру!]({f'https://www.twitch.tv/{login}'})**",
            url=f"https://www.twitch.tv/{login}",
            color=0x9146FF
        )
        
        if thumbnail_url:
            embed.set_image(url=f"{thumbnail_url}?t={int(discord.utils.utcnow().timestamp())}")
            
        embed.set_thumbnail(url="https://w7.pngwing.com/pngs/399/867/png-transparent-twitch-logo-streaming-media-twitch-logo-miscellaneous-purple-text-thumbnail.png")
        return embed

    async def get_announce_channels(self):
        channel = None
        if self.announce_channel_id and self.announce_channel_id.isdigit():
            channel = self.bot.get_channel(int(self.announce_channel_id))
            
        channels_to_send = []
        if not channel:
            for guild in self.bot.guilds:
                sys_chan = guild.system_channel
                if sys_chan and sys_chan.permissions_for(guild.me).send_messages:
                    channels_to_send.append(sys_chan)
                else:
                    for text_channel in guild.text_channels:
                        name = text_channel.name.lower()
                        if any(x in name for x in ['уведомления', 'стримы', 'основной']):
                            if text_channel.permissions_for(guild.me).send_messages:
                                channels_to_send.append(text_channel)
                                break
                    else:
                        first_valid = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
                        if first_valid:
                            channels_to_send.append(first_valid)
        else:
            channels_to_send.append(channel)
        return channels_to_send

    async def announce_stream(self, login, stream_info):
        self.stream_states[login]["messages"] = []
        embed = self.build_embed(login, stream_info)
        
        channels_to_send = await self.get_announce_channels()
        
        if login == self.main_channel:
            msg_content = "@everyone 📢 Я в эфире! Налетай:"
        else:
            msg_content = f"@everyone 📢 Пока я оффлайн, мой друг **{login}** ворвался в эфир! Зацените:"
            
        for c in channels_to_send:
            try:
                msg = await c.send(content=msg_content, embed=embed)
                self.stream_states[login]["messages"].append({"c": msg.channel.id, "m": msg.id})
            except Exception as e:
                logging.error(f"Failed to send stream announcement: {e}")

    async def update_stream(self, login, stream_info):
        msgs = await self.get_announce_messages(login)
        if not msgs:
            return
        embed = self.build_embed(login, stream_info)
        for msg in msgs:
            try:
                await msg.edit(embed=embed)
            except Exception as e:
                logging.error(f"Failed to update stream message: {e}")
                
    async def end_stream(self, login):
        msgs = await self.get_announce_messages(login)
        for msg in msgs:
            try:
                # Если это главный стример (твой аккаунт)
                if login == self.main_channel:
                    embed = msg.embeds[0]
                    embed.title = f"🔴 {login} закончил стрим."
                    friends_links = "\n".join([f"• [{f}](https://www.twitch.tv/{f})" for f in self.friend_channels])
                    embed.description = f"Трансляция завершена. Спасибо всем, кто смотрел!\n\n**Пока меня нет, заглядывайте к моим друзьям:**\n{friends_links}"
                    embed.set_image(url=None)
                    embed.color = discord.Color.dark_grey()
                    await msg.edit(content="Стрим завершен.", embed=embed)
                else:
                    # Если стрим друга закончился, удаляем уведомление
                    await msg.delete()
            except discord.NotFound:
                pass
            except Exception as e:
                logging.error(f"Failed to end stream message: {e}")
        
        if login != self.main_channel:
            # Для друзей полностью очищаем список сообщений, так как они удалены
            self.stream_states[login]["messages"] = []

async def setup(bot):
    await bot.add_cog(TwitchNotifier(bot))
