import os
import asyncio
import discord
from easy_pil import Editor, Canvas, load_image_async, Font
from utils.achievements_data import ACHIEVEMENTS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

async def generate_profile_card(member: discord.Member, level: int, xp: int, vibecoins: int, rank_name: str, bg_color: str = "#2b2d31", user_achievements: list = None):
    if user_achievements is None:
        user_achievements = []
        
    bg_path = os.path.join(BASE_DIR, "assets", "img", "default_bg.jpg")
    font_bold_path = os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Bold.ttf")
    font_med_path = os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Medium.ttf")
    font_reg_path = os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Regular.ttf")

    # Базовый фон
    try:
        if os.path.exists(bg_path):
            background = Editor(bg_path).resize((900, 350))
        else:
            background = Editor(Canvas((900, 350), color="#1e1f22"))
            
        # Панель "стеклянная" на которой все находится (как у джунипер бота)
        background.rectangle((20, 20), width=860, height=310, color=(0, 0, 0, 150), radius=20)
    except Exception as e:
        print(f"Background error: {e}")
        background = Editor(Canvas((900, 350), color="#2b2d31"))

    # Загружаем шрифты
    font_title = Font(path=font_bold_path, size=46)
    font_rank = Font(path=font_bold_path, size=28)
    font_level = Font(path=font_med_path, size=42)
    font_text = Font(path=font_reg_path, size=22)
    font_small = Font(path=font_reg_path, size=18)
    
    # АВАТАРКА
    try:
        avatar_image = await load_image_async(str(member.display_avatar.url))
        avatar = Editor(avatar_image).resize((180, 180)).circle_image()
        # Обводка белая или серая
        background.ellipse((35, 35), width=190, height=190, color="#ffffff")
        background.paste(avatar, (40, 40))
        
        # Добавляем кружок статуса! (online, dnd, idle, offline)
        status_colors = {
            discord.Status.online: "#43B581",
            discord.Status.idle: "#FAA61A",
            discord.Status.dnd: "#F04747",
            discord.Status.offline: "#747F8D",
            discord.Status.invisible: "#747F8D"
        }
        # У объекта Member не всегда 100% статус доступен, если не включены Presences, 
        # но если включены, берем его. По дефолту серый.
        user_status = getattr(member, 'status', discord.Status.offline)
        s_color = status_colors.get(user_status, "#747F8D")
        
        # Черный круг в качестве рамки для цвета
        background.ellipse((165, 165), width=50, height=50, color="#1e1f22")
        # Сам кружок статуса
        background.ellipse((170, 170), width=40, height=40, color=s_color)

    except Exception as e:
        print(f"Error loading avatar: {e}")
    
    start_x = 260
    
    # Имя и Ранг
    background.text((start_x, 40), str(member.display_name), font=font_title, color="#ffffff")
    background.text((start_x, 90), f"РАНГ: {rank_name}", font=font_rank, color="#57F287")
    
    # Уровень
    background.text((start_x, 140), "УР.", font=font_text, color="#aaaaaa")
    background.text((start_x + 35, 130), str(level), font=font_level, color="#ffffff")
    
    # Коины
    background.text((start_x + 100, 145), f"VibeCoins: {vibecoins} 🪙", font=font_text, color="#F1C40F")

    # ПОЛОСКА ОПЫТА (STATUS BAR)
    next_level_xp = ((level + 1) / 0.1) ** 2
    percentage = min(max((xp / next_level_xp) * 100, 0), 100) if next_level_xp > 0 else 0
    
    xp_text = f"{int(xp)} / {int(next_level_xp)} XP"
    # Пишем текст EXP справа над полоской
    background.text((840, 150), xp_text, font=font_text, color="#ffffff", align="right")
    
    # Сама полоска EXP мощная и округлая
    background.bar(
        (start_x, 185), 
        max_width=580, 
        height=35, 
        percentage=percentage, 
        color="#F1C40F", # Желто-оранжевая как в Джунипер
        radius=17
    )
    
    # АЧИВКИ (ТРОФЕИ)
    background.text((start_x, 245), "ТРОФЕИ:", font=font_text, color="#aaaaaa")
    
    async def draw_medal(ach_id, index):
        if ach_id in ACHIEVEMENTS:
            try:
                url = ACHIEVEMENTS[ach_id]["icon_url"]
                icon_img = await load_image_async(url)
                icon = Editor(icon_img).resize((45, 45))
                x_pos = start_x + 100 + (index * 60)
                background.paste(icon, (x_pos, 240))
            except Exception as e:
                print(f"Failed to load medal {ach_id}: {e}")

    if user_achievements:
        tasks = [draw_medal(ach, idx) for idx, ach in enumerate(user_achievements)]
        if tasks:
            await asyncio.gather(*tasks)
    else:
        background.text((start_x + 100, 247), "Пока пусто...", font=font_small, color="#555555")
            
    return background.image_bytes
