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
        
    theme_lvl = (level // 5) * 5
    theme_color = LEVEL_THEMES.get(theme_lvl, LEVEL_THEMES[max(k for k in LEVEL_THEMES.keys() if k <= level)])
    
    panel_opacity = min(160 + (level // 5) * 4, 230)

    bg_filename = f"bg_lvl_{theme_lvl}.jpg"
    bg_path = os.path.join(BASE_DIR, "assets", "img", bg_filename)
    
    if not os.path.exists(bg_path):
        bg_path = os.path.join(BASE_DIR, "assets", "img", "default_bg.jpg")

    font_bold_path = os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Bold.ttf")
    font_reg_path = os.path.join(BASE_DIR, "assets", "fonts", "Roboto-Regular.ttf")

    # Создаем холст
    try:
        if os.path.exists(bg_path):
            background = Editor(bg_path).resize((900, 350))
        else:
            background = Editor(Canvas((900, 350), color="#1e1f22"))
    except:
        background = Editor(Canvas((900, 350), color="#2b2d31"))

    # Стеклянная панель
    background.rectangle((20, 20), width=860, height=310, color=(0, 0, 0, panel_opacity), radius=20)
    
    font_title = Font(path=font_bold_path, size=46)
    font_rank = Font(path=font_bold_path, size=24)
    font_level = Font(path=font_bold_path, size=32)
    font_text = Font(path=font_reg_path, size=20)
    font_small = Font(path=font_reg_path, size=16)
    
    # АВАТАРКА
    try:
        avatar_image = await load_image_async(str(member.display_avatar.url))
        avatar = Editor(avatar_image).resize((180, 180)).circle_image()
        background.ellipse((35, 35), width=190, height=190, color=theme_color)
        background.paste(avatar, (40, 40))
        
        status_colors = {
            discord.Status.online: "#43B581",
            discord.Status.idle: "#FAA61A",
            discord.Status.dnd: "#F04747",
            discord.Status.offline: "#747F8D",
            discord.Status.invisible: "#747F8D"
        }
        s_color = status_colors.get(getattr(member, 'status', discord.Status.offline), "#747F8D")
        background.ellipse((168, 168), width=50, height=50, color="#2b2d31")
        background.ellipse((173, 173), width=40, height=40, color=s_color)
    except: pass
    
    start_x = 250
    
    safe_name = ''.join(c for c in member.display_name if ord(c) < 10000).strip()[:20]
    if not safe_name: safe_name = "User"
    
    safe_rank = ''.join(c for c in rank_name if ord(c) < 10000).strip()
    safe_rank = safe_rank.replace("[]", "").strip()
    
    background.text((start_x, 40), safe_name, font=font_title, color="#ffffff")
    background.text((start_x, 95), f"РАНГ: {safe_rank}", font=font_rank, color=theme_color)
    
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

    background.text((start_x, 125), f"VibeКоины: {vibecoins:,}", font=font_text, color="#F1C40F")
    v_hours = voice_seconds // 3600
    v_mins = (voice_seconds % 3600) // 60
    background.text((start_x + 220, 125), f"В голосе: {v_hours}ч {v_mins:02d}м", font=font_text, color="#A6A1FD")

    background.text((start_x, 160), "УР.", font=font_small, color="#aaaaaa")
    background.text((start_x + 30, 150), str(level), font=font_level, color="#ffffff")
    
    current_level_xp = (level / 0.023) ** 2
    next_level_xp = ((level + 1) / 0.023) ** 2
    xp_in_level = max(xp - current_level_xp, 0)
    xp_needed = next_level_xp - current_level_xp
    percentage = min(max((xp_in_level / xp_needed) * 100, 0), 100) if xp_needed > 0 else 0
    
    background.bar((start_x, 185), max_width=590, height=30, percentage=100, color="#313338", radius=15)
    
    if percentage > 0:
        background.bar((start_x, 185), max_width=590, height=30, percentage=percentage, color=theme_color, radius=15)
        
    background.text((840, 155), f"{int(xp):,} / {int(next_level_xp):,} XP", font=font_text, color="#ffffff", align="right")

    # ТРОФЕИ (возвращаем старый красивый рендер)
    background.text((start_x, 240), "ТРОФЕИ:", font=font_small, color="#aaaaaa")

    RARITY_ORDER = {"legendary": 4, "epic": 3, "rare": 2, "common": 1}
    RARITY_COLORS = {
        "common": "#95a5a6",   # серый
        "rare": "#3498db",     # синий
        "epic": "#9b59b6",     # фиолетовый
        "legendary": "#f1c40f",# золотой
        "mythic": "#e74c3c"    # красный
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

                # Отрисовка обводки
                background.ellipse((x_pos - 4, 226), width=48, height=48, color=ring_color)
                # Вырез
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
        background.text((start_x + 90, 240), "Пока нет трофеев...", font=font_small, color="#555555")

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
