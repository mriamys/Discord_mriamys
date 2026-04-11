from easy_pil import Editor, Canvas, load_image_async, Font
import discord
import os
import asyncio
from utils.achievements_data import ACHIEVEMENTS

async def generate_profile_card(member: discord.Member, level: int, xp: int, vibecoins: int, rank_name: str, bg_color: str = "#2b2d31", user_achievements: list = None):
    if user_achievements is None:
        user_achievements = []
        
    # Базовый фон
    try:
        background = Editor("assets/img/default_bg.jpg").resize((900, 350))
        # Затенение фона для читаемости
        background.rectangle((0, 0), width=900, height=350, color=(0, 0, 0, 190))
    except Exception:
        # Резервный фон
        background = Editor(Canvas((900, 350), color="#1e1f22"))
    
    # Шрифты с поддержкой кириллицы
    font_xl = Font(path="assets/fonts/Roboto-Bold.ttf", size=50)
    font_bold = Font(path="assets/fonts/Roboto-Bold.ttf", size=32)
    font_reg = Font(path="assets/fonts/Roboto-Medium.ttf", size=24)
    font_small = Font(path="assets/fonts/Roboto-Regular.ttf", size=20)
    
    # АВАТАРКА
    try:
        avatar_image = await load_image_async(str(member.display_avatar.url))
        avatar = Editor(avatar_image).resize((200, 200)).circle_image()
        # "Обводка" аватарки (рисуем круг чуть больше)
        background.ellipse((45, 45), width=210, height=210, color="#57F287")
        background.paste(avatar, (50, 50))
    except Exception as e:
        print(f"Error loading avatar: {e}")
    
    start_x = 300
    
    # ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ
    background.text((start_x, 50), str(member.display_name), font=font_xl, color="#ffffff")
    background.text((start_x, 110), str(rank_name), font=font_bold, color="#57F287")
    
    # Экономика и Уровень
    background.text((start_x, 160), f"VibeCoins: {vibecoins} 🪙", font=font_reg, color="#f1c40f")
    background.text((start_x + 350, 160), f"УРОВЕНЬ {level}", font=font_bold, color="#ffffff")
    
    # ПОЛОСКА ОПЫТА (STATUS BAR)
    next_level_xp = ((level + 1) / 0.1) ** 2
    percentage = min(max((xp / next_level_xp) * 100, 0), 100) if next_level_xp > 0 else 0
    
    background.text((start_x, 200), f"{int(xp)} XP", font=font_small, color="#aaaaaa")
    background.text((start_x + 450, 200), f"{int(next_level_xp)} XP", font=font_small, color="#aaaaaa")
    
    background.bar(
        (start_x, 230), 
        max_width=520, 
        height=30, 
        percentage=percentage, 
        color="#ED4245", 
        radius=15
    )
    
    # АЧИВКИ (ТРОФЕИ)
    background.text((start_x, 280), "ТРОФЕИ:", font=font_reg, color="#ffffff")
    
    async def draw_medal(ach_id, index):
        if ach_id in ACHIEVEMENTS:
            try:
                url = ACHIEVEMENTS[ach_id]["icon_url"]
                icon_img = await load_image_async(url)
                icon = Editor(icon_img).resize((40, 40))
                x_pos = start_x + 110 + (index * 55)
                background.paste(icon, (x_pos, 275))
            except Exception as e:
                print(f"Failed to load medal {ach_id}: {e}")

    if user_achievements:
        tasks = [draw_medal(ach, idx) for idx, ach in enumerate(user_achievements)]
        if tasks:
            await asyncio.gather(*tasks)
    else:
        background.text((start_x + 110, 282), "Пока пусто...", font=font_small, color="#555555")
            
    return background.image_bytes
