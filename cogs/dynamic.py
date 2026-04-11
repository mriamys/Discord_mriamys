import discord
from discord.ext import commands
import logging

class DynamicRooms(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Названия каналов-триггеров, при заходе в которые создается комната
        self.trigger_channel_names = ["➕ создать комнату", "➕ create", "➕ приват", "создать комнату"]
        self.dynamic_channels = [] # Список ID созданных комнат

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # 1. Зашел в канал создания
        if after.channel is not None and any(t in after.channel.name.lower() for t in self.trigger_channel_names):
            category = after.channel.category
            guild = after.channel.guild
            
            try:
                # Создаем новую комнату
                new_channel = await guild.create_voice_channel(
                    name=f"🎮┃{member.display_name}",
                    category=category,
                    user_limit=0
                )
                self.dynamic_channels.append(new_channel.id)
                
                # Перемещаем пользователя туда
                await member.move_to(new_channel)
                
                # Даем ему права управлять каналом
                await new_channel.set_permissions(member, manage_channels=True, manage_permissions=True)
                logging.info(f"Created dynamic channel for {member.display_name}")
            except Exception as e:
                logging.error(f"Failed to create dynamic channel: {e}")

        # 2. Вышел из динамического канала (удаляем если пустой)
        if before.channel is not None and before.channel.id in self.dynamic_channels:
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete(reason="Dynamic room is empty")
                    self.dynamic_channels.remove(before.channel.id)
                    logging.info("Deleted empty dynamic channel")
                except Exception as e:
                    logging.error(f"Failed to delete dynamic channel: {e}")

async def setup(bot):
    await bot.add_cog(DynamicRooms(bot))
