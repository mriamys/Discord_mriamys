import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Color mapping (Role ID or Name fragment -> Hex Color)
# Discord uses decimal colors, so we'll convert hex to decimal.
def hex_to_int(hex_str):
    return int(hex_str.lstrip('#'), 16)

STAFF_COLORS = {
    772539582649597952: "#FFD700", # [👑] Владелец
    767764611805216818: "#E91E63", # админ
    771354655014780968: "#3498DB", # модератор
    1492577933523419327: "#1ABC9C", # Программист
    1491429454394953879: "#1ABC9C", # VibeCoding
    767768121037422627: "#FFD700", # vip (User might want gold for vip too)
    1491572802937950228: "#FF69B4", # ЖЕНЩИНА
}

SOCIAL_COLORS = {
    1492543261980495993: "#6441A5", # [🎥] Стример (Twitch Purple)
    1492543263608017159: "#FF0000", # [🎞️] Ютубер (YouTube Red)
    1492543265231339571: "#00F2EA", # [📱] Тик-токер (TikTok Teal)
}

CODER_COLORS = {
    1492550410823536651: "#3776AB", # Python Coder
    1492550485113180200: "#E34F26", # CSS Coder (mapped to HTML color)
    1492550487373779008: "#E34F26", # HTML Coder
    1492555242795962490: "#F7DF1E", # JavaScript Coder
    1492577931573067987: "#3178C6", # TypeScript Coder
}

# Ranks Gradient Mapping (by level)
RANK_GRADIENT = {
    100: "#2E0854", # Absolute
    90: "#4B0082",
    80: "#4B0082",
    75: "#483D8B",
    70: "#1F75FE", # Legend
    65: "#1F75FE",
    60: "#1E90FF",
    55: "#2ECC71", # Sigma
    50: "#2ECC71",
    45: "#27AE60",
    40: "#27AE60",
    35: "#2196F3",
    30: "#2190F3",
    25: "#95A5A6", # Norsmis
    20: "#95A5A6",
    15: "#7F8C8D",
    10: "#7F8C8D",
    5: "#9E9E9E",
    0: "#3E2723", # Cringe
}

async def apply_colors():
    intents = discord.Intents.all()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Logged in as {client.user}")
        guild = client.guilds[0]
        
        roles = guild.roles
        my_role = guild.me.top_role
        
        print(f"Top role position: {my_role.position}")

        for role in roles:
            if role.is_default() or role.managed: continue
            if role.position >= my_role.position:
                print(f"Skipping {role.name} - cannot manage.")
                continue

            new_color_hex = None

            # 1. Staff
            if role.id in STAFF_COLORS:
                new_color_hex = STAFF_COLORS[role.id]
            # 2. Social
            elif role.id in SOCIAL_COLORS:
                new_color_hex = SOCIAL_COLORS[role.id]
            # 3. Coders
            elif role.id in CODER_COLORS:
                new_color_hex = CODER_COLORS[role.id]
            # 4. Ranks
            else:
                # Try to find emoji for ranks
                from cogs.leveling import MEME_RANKS
                # Reverse mapping search
                level = None
                for lvl, name in MEME_RANKS.items():
                    # Check if role matches emoji or name fragment
                    if name in role.name:
                        level = lvl
                        break
                
                if level is not None and level in RANK_GRADIENT:
                    new_color_hex = RANK_GRADIENT[level]

            if new_color_hex:
                new_color = discord.Color(hex_to_int(new_color_hex))
                if role.color != new_color:
                    print(f"Updating {role.name} to {new_color_hex}")
                    try:
                        await role.edit(color=new_color)
                        await asyncio.sleep(0.5) # Rate limit safety
                    except Exception as e:
                        print(f"Error updating {role.name}: {e}")
                else:
                    print(f"Role {role.name} already has correct color.")

        print("Done!")
        await client.close()

    await client.start(TOKEN)

if __name__ == "__main__":
    from sys import path
    path.append(".")
    asyncio.run(apply_colors())
