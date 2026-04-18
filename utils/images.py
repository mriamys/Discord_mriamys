import os
import asyncio
import discord
from easy_pil import Editor, Canvas, load_image_async, Font
from utils.achievements_data import ACHIEVEMENTS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Цветовые схемы каждые 5 уровней
LEVEL_THEMES = {
    0:  "#95a5a6", 5:  "#57F287", 10: "#1abc9c", 15: "#11806a",
    20: "#3498db", 25: "#206694", 30: "#9b59b6", 35: "#71368a",
    40: "#e91e63", 45: "#ad1457", 50: "#e74c3c", 55: "#992d22",
    60: "#e67e22", 65: "#a84300", 70: "#f1c40f", 75: "#c27c0e",
    80: "#1f2c39", 85: "#34495e", 90: "#000000", 95: "#7289da", 100: "#ffffff"
}

async def generate_profile_card(member: discord.Member, level: int, xp: int, vibecoins: int, voice_seconds: int, rank_name: str, bg_color: str = "#2b2d31", user_achievements: list = None, streak: int = 0):
    if user_achievements is None:
        user_achievements = []
        
    # Определяем тему на основе уровня (каждые 5 уровней)
    theme_lvl = (level // 5) * 5
    theme_color = LEVEL_THEMES.get(theme_lvl, LEVEL_THEMES[max(k for k in LEVEL_THEMES.keys() if k <= level)])
    
    # Прозрачность панели слегка растет с уровнем
    panel_opacity = min(160 + (level // 5) * 4, 230)

    # Путь к фону по шагу 5
    bg_filename = f"bg_lvl_{theme_lvl}.jpg"
    bg_path = os.path.join(BASE_DIR, "assets", "img", bg_filename)
    
    if not os.path.exists(bg_path):
        bg_path = os.path.join(BASE_DIR, "assets", "img", "default_bg.jpg")

    font_bold_path = os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Bold.ttf")
    font_reg_path = os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Regular.ttf")

    # Создаем холст
    try:
        if os.path.exists(bg_path):
            background = Editor(bg_path).resize((900, 380))
        else:
            background = Editor(Canvas((900, 380), color="#1e1f22"))
    except:
        background = Editor(Canvas((900, 380), color="#2b2d31"))

    # Стеклянная панель
    background.rectangle((20, 20), width=860, height=340, color=(0, 0, 0, panel_opacity), radius=20)
    
    font_title = Font(path=font_bold_path, size=40)
    font_rank = Font(path=font_bold_path, size=22)
    font_level = Font(path=font_bold_path, size=30)
    font_text = Font(path=font_reg_path, size=18)
    font_small = Font(path=font_reg_path, size=14)
    
    # АВАТАРКА
    try:
        avatar_image = await load_image_async(str(member.display_avatar.url))
        avatar = Editor(avatar_image).resize((160, 160)).circle_image()
        background.ellipse((35, 35), width=170, height=170, color=theme_color)
        background.paste(avatar, (40, 40))
        
        # Статус
        status_colors = {
            discord.Status.online: "#43B581",
            discord.Status.idle: "#FAA61A",
            discord.Status.dnd: "#F04747",
            discord.Status.offline: "#747F8D",
            discord.Status.invisible: "#747F8D"
        }
        s_color = status_colors.get(getattr(member, 'status', discord.Status.offline), "#747F8D")
        background.ellipse((155, 155), width=45, height=45, color="#111111")
        background.ellipse((160, 160), width=35, height=35, color=s_color)
    except: pass
    
    start_x = 230
    
    # Имя и Ранг
    safe_name = ''.join(c for c in member.display_name if ord(c) < 10000).strip()[:20]
    background.text((start_x, 45), safe_name, font=font_title, color="#ffffff")
    background.text((start_x, 90), f"РАНГ: {rank_name}", font=font_rank, color=theme_color)
    
    # Стрик
    if streak > 0:
        background.text((840, 90), f"Стрик: {streak} 🔥", font=font_rank, color="#FF5733", align="right")

    # Статистика
    background.text((start_x, 120), f"VibeКоины: {vibecoins:,}", font=font_text, color="#F1C40F")
    v_hours = voice_seconds // 3600
    v_mins = (voice_seconds % 3600) // 60
    background.text((start_x + 200, 120), f"В голосе: {v_hours}ч {v_mins}м", font=font_text, color="#A6A1FD")

    # Уровень и полоска
    background.text((start_x, 155), f"УРОВЕНЬ {level}", font=font_level, color="#ffffff")
    
    current_level_xp = (level / 0.023) ** 2
    next_level_xp = ((level + 1) / 0.023) ** 2
    xp_in_level = max(xp - current_level_xp, 0)
    xp_needed = next_level_xp - current_level_xp
    percentage = min(max((xp_in_level / xp_needed) * 100, 0), 100) if xp_needed > 0 else 0
    
    background.bar((start_x, 190), max_width=610, height=25, percentage=100, color="#333333", radius=12)
    background.bar((start_x, 190), max_width=610, height=25, percentage=percentage, color=theme_color, radius=12)
    background.text((840, 170), f"{int(xp):,} / {int(next_level_xp):,} XP", font=font_small, color="#aaaaaa", align="right")

    # ТРОФЕИ
    background.text((40, 240), "ТРОФЕИ И ДОСТИЖЕНИЯ", font=font_rank, color="#ffffff")
    background.rectangle((40, 265), width=820, height=80, color=(255, 255, 255, 20), radius=10)
    
    if user_achievements:
        ach_x = 55
        ach_y = 285
        count = 0
        # Сортируем ачивки по редкости или порядку получения
        for ach_id in user_achievements:
            if ach_id in ACHIEVEMENTS:
                ach_data = ACHIEVEMENTS[ach_id]
                background.text((ach_x, ach_y), ach_data.get('emoji', '🏆'), font=font_level, color="#ffffff")
                ach_x += 50
                count += 1
                if count >= 16: break
    else:
        background.text((60, 295), "Выполняй задания и проявляй актив, чтобы получить трофеи!", font=font_text, color="#888888")

    return background.image_bytes

async def generate_welcome_card(member: discord.Member):
    background = Editor(Canvas((800, 250), color="#2b2d31"))
    try:
        avatar_image = await load_image_async(str(member.display_avatar.url))
        avatar = Editor(avatar_image).resize((150, 160)).circle_image()
        background.paste(avatar, (40, 45))
    except: pass
    
    font_title = Font(path=os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Bold.ttf"), size=40)
    background.text((220, 80), f"Добро пожаловать,", font=font_title, color="#ffffff")
    background.text((220, 130), f"{member.display_name}!", font=font_title, color="#57F287")
    return background.image_bytes
