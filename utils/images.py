from easy_pil import Editor, Canvas, load_image_async, Font
import discord
import os
import asyncio
from utils.achievements_data import ACHIEVEMENTS

async def generate_profile_card(member: discord.Member, level: int, xp: int, vibecoins: int, rank_name: str, bg_color: str = "#2b2d31", user_achievements: list = None):
    if user_achievements is None:
        user_achievements = []
        
    # Создаем фон, увеличили высоту до 350 для кубков
    background = Editor(Canvas((900, 350), color=bg_color))
    
    try:
        # Загружаем аватар пользователя
        avatar_image = await load_image_async(str(member.display_avatar.url))
        avatar = Editor(avatar_image).resize((200, 200)).circle_image()
        background.paste(avatar, (50, 50))
    except Exception as e:
        print(f"Error loading avatar: {e}")
    
    # Шрифты встроенные в easy_pil
    font_title = Font.poppins(size=50, variant="bold")
    font_subtitle = Font.poppins(size=35, variant="regular")
    font_small = Font.poppins(size=25, variant="light")
    
    # Текст
    background.text((300, 50), str(member.display_name), font=font_title, color="white")
    background.text((300, 120), str(rank_name), font=font_subtitle, color="#57F287")
    background.text((300, 180), f"VibeCoins: {vibecoins} 🪙 | XP: {xp}", font=font_small, color="white")
    
    # Полоска опыта (Progress Bar)
    next_level_xp = ((level + 1) / 0.1) ** 2
    if next_level_xp > 0:
        percentage = min(max((xp / next_level_xp) * 100, 0), 100)
    else:
        percentage = 0
        
    background.bar(
        (300, 230), 
        max_width=550, 
        height=30, 
        percentage=percentage, 
        color="#ED4245", 
        radius=15
    )
    
    # Отрисовка Трофеев (Кубков) снизу
    start_x = 300
    start_y = 280
    
    async def draw_medal(ach_id, index):
        if ach_id in ACHIEVEMENTS:
            try:
                url = ACHIEVEMENTS[ach_id]["icon_url"]
                icon_img = await load_image_async(url)
                icon = Editor(icon_img).resize((40, 40))
                # Вычисляем позицию
                x_pos = start_x + (index * 55)
                background.paste(icon, (x_pos, start_y))
            except Exception as e:
                print(f"Failed to load medal {ach_id}: {e}")

    if user_achievements:
        background.text((50, 290), "Трофеи:", font=font_small, color="#aaaaaa")
        # Параллельно загружаем и рисуем все медали
        tasks = []
        for idx, ach in enumerate(user_achievements):
            tasks.append(draw_medal(ach, idx))
        if tasks:
            await asyncio.gather(*tasks)
            
    return background.image_bytes
