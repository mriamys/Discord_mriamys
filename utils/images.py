import os
import asyncio
import discord
from easy_pil import Editor, Canvas, load_image_async, Font
from utils.achievements_data import ACHIEVEMENTS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

async def generate_profile_card(member: discord.Member, level: int, xp: int, vibecoins: int, voice_seconds: int, rank_name: str, bg_color: str = "#2b2d31", user_achievements: list = None, streak: int = 0):
    if user_achievements is None:
        user_achievements = []
        
    bg_path = os.path.join(BASE_DIR, "assets", "img", "default_bg.jpg")
    font_bold_path = os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Bold.ttf")
    font_med_path = os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Medium.ttf")
    font_reg_path = os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Regular.ttf")

    try:
        if os.path.exists(bg_path):
            background = Editor(bg_path).resize((900, 350))
        else:
            background = Editor(Canvas((900, 350), color="#1e1f22"))
            
        # Панель "стеклянная"
        background.rectangle((20, 20), width=860, height=310, color=(0, 0, 0, 160), radius=20)
    except Exception as e:
        print(f"Background error: {e}")
        background = Editor(Canvas((900, 350), color="#2b2d31"))

    font_title = Font(path=font_bold_path, size=46)
    font_rank = Font(path=font_bold_path, size=24)
    font_level = Font(path=font_bold_path, size=32)
    font_text = Font(path=font_reg_path, size=20)
    font_small = Font(path=font_reg_path, size=16)
    
    # АВАТАРКА
    try:
        avatar_image = await load_image_async(str(member.display_avatar.url))
        avatar = Editor(avatar_image).resize((180, 180)).circle_image()
        # Обводка
        background.ellipse((35, 35), width=190, height=190, color="#ffffff")
        background.paste(avatar, (40, 40))
        
        status_colors = {
            discord.Status.online: "#43B581",
            discord.Status.idle: "#FAA61A",
            discord.Status.dnd: "#F04747",
            discord.Status.offline: "#747F8D",
            discord.Status.invisible: "#747F8D"
        }
        user_status = getattr(member, 'status', discord.Status.offline)
        s_color = status_colors.get(user_status, "#747F8D")
        
        # Статус четко внизу справа аватарки
        # Центр 130,130, радиус 90. offset = 90 * cos(45deg)=63. 130+63=193 (центр кружка)
        # Радиус кружка 20 -> top-left = 173,173
        background.ellipse((168, 168), width=50, height=50, color="#2b2d31") # вырез
        background.ellipse((173, 173), width=40, height=40, color=s_color)

    except Exception as e:
        print(f"Error loading avatar: {e}")
    
    start_x = 250
    
    # Очищаем от эмодзи, чтобы не было квадратиков (удаляем все символы с кодом > 10000, эмодзи обычно высоко)
    safe_name = ''.join(c for c in member.display_name if ord(c) < 10000).strip()
    if not safe_name: safe_name = "User"
        
    safe_rank = ''.join(c for c in rank_name if ord(c) < 10000).strip()
    safe_rank = safe_rank.replace("[]", "").strip()
    
    # Имя и Ранг
    background.text((start_x, 40), safe_name, font=font_title, color="#ffffff")
    background.text((start_x, 95), f"РАНГ: {safe_rank}", font=font_rank, color="#57F287")
    
    if streak > 0:
        streak_text = f"Стрик: {streak}"
        background.text((840, 95), streak_text, font=font_rank, color="#FF5733", align="right")
        try:
            from PIL import ImageDraw
            draw = ImageDraw.Draw(background.image)
            text_bbox = draw.textbbox((0, 0), streak_text, font=font_rank.font)
            text_w = text_bbox[2] - text_bbox[0]
            
            fire_img_path = os.path.join(BASE_DIR, "assets", "img", "fire.png")
            if os.path.exists(fire_img_path):
                fire_icon = Editor(fire_img_path).resize((24, 24))
                fire_x = 835 - text_w - 28 # Add margin
                background.paste(fire_icon, (fire_x, 95))
        except Exception as e:
            print(f"Fire icon error: {e}")    
    # Уровень, Коины, XP текст
    background.text((start_x, 155), "УР.", font=font_small, color="#aaaaaa")
    background.text((start_x + 30, 145), str(level), font=font_level, color="#ffffff")
    
    background.text((start_x + 80, 155), f"Коины: {vibecoins}", font=font_text, color="#F1C40F")

    v_hours = voice_seconds // 3600
    v_mins = (voice_seconds % 3600) // 60
    voice_str = f"Голос: {v_hours}ч {v_mins:02d}м"
    background.text((start_x + 240, 155), voice_str, font=font_text, color="#3498db")

    next_level_xp = ((level + 1) / 0.023) ** 2
    percentage = min(max((xp / next_level_xp) * 100, 0), 100) if next_level_xp > 0 else 0
    
    xp_text = f"{int(xp)} / {int(next_level_xp)} XP"
    background.text((840, 155), xp_text, font=font_text, color="#ffffff", align="right")
    
    # ПОЛОСКА ОПЫТА (Двойная: подложка + прогресс)
    # 1. Трэк (пустая серая)
    background.bar(
        (start_x, 185), 
        max_width=590, 
        height=30, 
        percentage=100, 
        color="#313338",
        radius=15
    )
    # 2. Сам прогресс
    if percentage > 0:
        background.bar(
            (start_x, 185), 
            max_width=590, 
            height=30, 
            percentage=percentage, 
            color="#F1C40F",
            radius=15
        )
    
    # АЧИВКИ (ТРОФЕИ)
    background.text((start_x, 240), "ТРОФЕИ:", font=font_small, color="#aaaaaa")
    
    RARITY_ORDER = {"legendary": 4, "epic": 3, "rare": 2, "common": 1}
    RARITY_COLORS = {
        "common": "#95a5a6",   # серый
        "rare": "#3498db",     # синий
        "epic": "#9b59b6",     # фиолетовый
        "legendary": "#f1c40f" # золотой
    }
    
    async def draw_medal(ach_id, index):
        if ach_id in ACHIEVEMENTS:
            try:
                ach_data = ACHIEVEMENTS[ach_id]
                url = ach_data["icon_url"]
                rarity = ach_data.get("rarity", "common")
                ring_color = RARITY_COLORS.get(rarity, "#95a5a6")
                
                icon_img = await load_image_async(url)
                icon = Editor(icon_img).resize((40, 40))
                
                x_pos = start_x + 90 + (index * 60)
                
                # Обводка
                background.ellipse((x_pos - 4, 226), width=48, height=48, color=ring_color)
                # Внутренний темный кружок под иконку
                background.ellipse((x_pos - 1, 229), width=42, height=42, color="#2b2d31")
                
                background.paste(icon, (x_pos, 230))
            except Exception as e:
                print(f"Failed to load medal {ach_id}: {e}")

    if user_achievements:
        sorted_ach = sorted(
            user_achievements,
            key=lambda x: RARITY_ORDER.get(ACHIEVEMENTS.get(x, {}).get("rarity", "common"), 0),
            reverse=True
        )
        display_achievements = sorted_ach[:8]
        
        tasks = [draw_medal(ach, idx) for idx, ach in enumerate(display_achievements)]
        if tasks:
            await asyncio.gather(*tasks)
            
        if len(user_achievements) > 8:
            extra = len(user_achievements) - 8
            x_pos = start_x + 90 + (8 * 60)
            background.text((x_pos + 10, 240), f"+{extra}", font=font_text, color="#f1c40f")
    else:
        background.text((start_x + 90, 240), "Пока пусто...", font=font_small, color="#555555")
            
    return background.image_bytes

async def generate_welcome_card(member: discord.Member) -> bytes:
    bg_path = os.path.join(BASE_DIR, "assets", "img", "default_bg.jpg")
    font_bold_path = os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Bold.ttf")
    font_reg_path = os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Regular.ttf")

    try:
        if os.path.exists(bg_path):
            background = Editor(bg_path).resize((800, 300))
        else:
            background = Editor(Canvas((800, 300), color="#1e1f22"))
            
        # Панель "стеклянная" в центре
        background.rectangle((20, 20), width=760, height=260, color=(0, 0, 0, 160), radius=20)
    except Exception as e:
        print(f"Background error: {e}")
        background = Editor(Canvas((800, 300), color="#2b2d31"))

    font_title = Font(path=font_bold_path, size=46)
    font_text = Font(path=font_reg_path, size=24)
    
    # АВАТАРКА
    try:
        avatar_image = await load_image_async(str(member.display_avatar.url))
        avatar = Editor(avatar_image).resize((180, 180)).circle_image()
        # Обводка
        background.ellipse((55, 55), width=190, height=190, color="#ffffff")
        background.paste(avatar, (60, 60))
    except Exception as e:
        print(f"Error loading avatar: {e}")
    
    def strip_emojis(text):
        if not text: return ""
        import re
        return re.sub(r'[^\w\s,\.\!\?\#\-\[\]\(\)\:]+', '', text)
        
    safe_name = strip_emojis(member.display_name)
    if not safe_name.strip(): safe_name = "User"
    
    text_start_x = 280
    
    # Текст ДОБРО ПОЖАЛОВАТЬ
    background.text((text_start_x, 90), "ДОБРО ПОЖАЛОВАТЬ", font=font_title, color="#57F287")
    background.text((text_start_x, 150), safe_name, font=font_text, color="#ffffff")
    
    # Номер участника
    member_count = len(member.guild.members)
    background.text((text_start_x, 200), f"Ты наш {member_count}-й участник!", font=font_text, color="#aaaaaa")
    
    return background.image_bytes
