from easy_pil import Editor, Canvas, Font, load_image_async
import asyncio

async def make_mockup():
    bg_color = "#2b2d31"
    background = Editor(Canvas((900, 300), color=bg_color))
    
    # Fake avatar (I will just draw a circle instead of downloading an avatar to avoid discord connection)
    avatar = Editor(Canvas((200, 200), color="#5865F2")).circle_image()
    
    font_title = Font.poppins(size=50, variant="bold")
    font_subtitle = Font.poppins(size=35, variant="regular")
    font_small = Font.poppins(size=25, variant="light")
    
    background.paste(avatar, (50, 50))
    background.text((300, 50), "Dima (Mriamys)", font=font_title, color="white")
    background.text((300, 120), "[⚡] Сигма", font=font_subtitle, color="#57F287")
    background.text((300, 180), "VibeCoins: 1337 🪙 | XP: 15400", font=font_small, color="white")
    
    background.bar((300, 230), max_width=550, height=30, percentage=65, color="#ED4245", radius=15)
    
    background.save("profile_example.png")

asyncio.run(make_mockup())
