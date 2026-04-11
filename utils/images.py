from easy_pil import Editor, Canvas, load_image_async, Font
import discord
import os

async def generate_profile_card(member: discord.Member, level: int, xp: int, vibecoins: int, rank_name: str, bg_color: str = "#2b2d31"):
    # Создаем фон
    background = Editor(Canvas((900, 300), color=bg_color))
    
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
    # XP = (Уровень / 0.1) ^ 2
    next_level_xp = ((level + 1) / 0.1) ** 2
    
    # Защита от деления на 0
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
    
    return background.image_bytes
