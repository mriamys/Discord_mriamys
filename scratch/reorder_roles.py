import discord
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Hierarchy groups (Top to Bottom)
# We will assign a group priority. Lower group_id = Higher position in Discord.
# Note: Discord positions are 1-based, higher number = higher list position.
# We will calculate positions from bottom up.

STAFF_ROLES = [
    772539582649597952, # [👑] Владелец
    767764611805216818, # админ
    771354655014780968, # модератор
    1492577933523419327, # Программист (Основная)
    1491429454394953879, # VibeCoding (Основная)
    767768121037422627, # vip
    767764498064736357, # самый главный олд
    1491572802937950228, # ЖЕНЩИНА
    771362794737369099, # резерв
    1492409941615710310, # serv
]

RANK_ROLES_LEVELS = {
    "🌌": 100, "🏋️": 90, "👑": 80, "🧔‍♂️": 75, "🌟": 70, "👵": 65, "🧚": 60,
    "⚡": 55, "🗿": 50, "👌": 45, "🔥": 40, "🕶️": 35, "🕺": 30, "🧘": 25,
    "🧔": 20, "🍺": 15, "👶": 10, "👞": 5, "🌫️": 0
}

SOCIAL_ROLES = [
    770256953845743636, # Twitch Subscriber
    770256953845743637, # Twitch Subscriber: Tier 1
    770256953845743638, # Twitch Subscriber: Tier 2
    770256953845743639, # Twitch Subscriber: Tier 3
    1492543261980495993, # [🎥] Стример
    1492543263608017159, # [🎞️] Ютубер
    1492543265231339571, # [📱] Тик-токер
]

CODER_INTERESTS = [
    1492550410823536651, # Python Coder
    1492550485113180200, # CSS Coder
    1492550487373779008, # HTML Coder
    1492555225754767381, # Java Coder
    1492555242795962490, # JavaScript Coder
    1492577931573067987, # TypeScript Coder
    1492614085739544626, # SQL Coder
    1492615893329645618, # Вайбкодер Coder
]

GAME_ROLES = [
    767764612832952421, # among us
    768909979909619802, # Fortnite
    771362053742657546, # CS:GO
    771362631180222535, # Grand Theft Auto V
    771363223152099348, # Grand Theft Auto: San Andreas
    771362442067574795, # Rust
    771361038247002112, # Rocket League
    835525408844808193, # Apex
    835529294453145631, # Valorant
    901521424915771482, # ets2
    1492555395280146483, # Minecraft
    1492597507597799629, # Euro Truck
]

async def reorder():
    intents = discord.Intents.all()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Logged in as {client.user}")
        guild = client.guilds[0]
        
        # Identification
        roles = guild.roles
        
        # Sort roles into categories
        staff = []
        bot_roles = []
        ranks = []
        social = []
        interests = []
        games = []
        others = []

        my_role = guild.me.top_role

        for role in roles:
            if role.is_default(): continue
            
            # Staff
            if role.id in STAFF_ROLES:
                staff.append(role)
            # Ranks
            elif any(emoji in role.name for emoji in RANK_ROLES_LEVELS.keys()):
                # Extract level from name or emoji
                level = -1
                for emoji, lvl in RANK_ROLES_LEVELS.items():
                    if emoji in role.name:
                        level = lvl
                        break
                ranks.append((level, role))
            # Social
            elif role.id in SOCIAL_ROLES:
                social.append(role)
            # Interests
            elif role.id in CODER_INTERESTS:
                interests.append(role)
            # Games
            elif role.id in GAME_ROLES:
                games.append(role)
            # Bot related (managed or specific roles)
            elif role.managed or "bot" in role.name.lower() or role.id == 767762940144517141:
                bot_roles.append(role)
            else:
                others.append(role)

        # Sorting within groups
        staff.sort(key=lambda r: STAFF_ROLES.index(r.id))
        ranks.sort(key=lambda x: x[0], reverse=True)
        ranks = [x[1] for x in ranks]
        social.sort(key=lambda r: SOCIAL_ROLES.index(r.id) if r.id in SOCIAL_ROLES else 99)
        interests.sort(key=lambda r: CODER_INTERESTS.index(r.id))
        games.sort(key=lambda r: GAME_ROLES.index(r.id))

        # FINAL ORDER (Top to Bottom)
        # 1. Staff
        # 2. Ranks (higher level first)
        # 3. Social
        # 4. Interests
        # 5. Games
        # 6. Bots (placed below games as per user "снизу")
        # BUT: Bot must be above RANKS and GAMES to manage them.
        # User said "роль бота снизу" - I take this as "lowest priority in staff" or "very bottom".
        # I will place the BOT role right above Ranks to ensure it works. 
        # Wait, user said "Ок" to my proposal of placing it above Ranks.

        new_order = []
        new_order.extend(staff)
        # Place bot role here to ensure it manages ranks and games
        for br in bot_roles:
            if br not in new_order: new_order.append(br)
        
        new_order.extend(ranks)
        new_order.extend(social)
        new_order.extend(interests)
        new_order.extend(games)
        
        # Add any others at the very bottom
        for o in others:
            if o not in new_order: new_order.append(o)

        print("\nPROPOSED ORDER (HIGHEST TO LOWEST):")
        for i, r in enumerate(new_order):
            print(f"{i+1}. {r.name}")

        # Applying changes
        # Pos 0 is everyone. Lowest role should be at Pos 1.
        # We need to reverse the list to assign positions (highest position = index 0 of reversed list)
        
        # dict of {role: position}
        # Discord position starts from 1. 
        # Actually edit_role_positions takes {role: position}
        
        # We'll assign positions from 1 up to len(new_order)
        # The first role in new_order should have position len(new_order)
        
        positions = {}
        total = len(new_order)
        for i, role in enumerate(new_order):
            # Only move if it's below our top role
            if role.position < my_role.position:
                positions[role] = total - i
            else:
                print(f"Skipping {role.name} - too high for me to move.")

        if positions:
            try:
                print("\nApplying changes...")
                await guild.edit_role_positions(positions=positions)
                print("Done!")
            except Exception as e:
                print(f"Error during edit: {e}")
        else:
            print("No roles to move.")
            
        await client.close()

    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(reorder())
