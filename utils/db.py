import aiomysql
import logging
import asyncio
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        try:
            self.pool = await aiomysql.create_pool(
                host=DB_HOST,
                port=3306,
                user=DB_USER,
                password=DB_PASS,
                db=DB_NAME,
                autocommit=True,
                cursorclass=aiomysql.DictCursor
            )
            logging.info("Connected to MySQL Database!")
        except Exception as e:
            logging.error(f"Database Connection Error: {e}")
            raise e

    async def init_tables(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Основная таблица пользователей
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id VARCHAR(25) PRIMARY KEY,
                        xp FLOAT DEFAULT 0,
                        level INT DEFAULT 0,
                        vibecoins INT DEFAULT 0,
                        msg_count INT DEFAULT 0,
                        shop_spent INT DEFAULT 0,
                        nick_changes INT DEFAULT 0,
                        voice_time_seconds INT DEFAULT 0,
                        xp_boost_until DATETIME DEFAULT NULL,
                        cases_opened INT DEFAULT 0,
                        duels_won INT DEFAULT 0,
                        memes_ordered INT DEFAULT 0,
                        voice_memes_until DATETIME DEFAULT NULL,
                        voice_memes_count INT DEFAULT 0,
                        quest_id VARCHAR(50) DEFAULT NULL,
                        quest_progress INT DEFAULT 0,
                        quest_target INT DEFAULT 0,
                        quest_reward_coins INT DEFAULT 0,
                        quest_reward_xp INT DEFAULT 0,
                        quest_date DATE DEFAULT NULL,
                        quests_completed INT DEFAULT 0,
                        bj_wins INT DEFAULT 0,
                        quiz_correct INT DEFAULT 0
                    )
                ''')
                
                # Таблица для глобальных настроек бота
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS global_settings (
                        `key` VARCHAR(50) PRIMARY KEY,
                        `value` VARCHAR(255)
                    )
                ''')
                
                # Миграции
                columns_to_add = [
                    ("msg_count", "INT DEFAULT 0"),
                    ("shop_spent", "INT DEFAULT 0"),
                    ("nick_changes", "INT DEFAULT 0"),
                    ("voice_time_seconds", "INT DEFAULT 0"),
                    ("xp_boost_until", "DATETIME DEFAULT NULL"),
                    ("cases_opened", "INT DEFAULT 0"),
                    ("duels_won", "INT DEFAULT 0"),
                    ("memes_ordered", "INT DEFAULT 0"),
                    ("voice_memes_until", "DATETIME DEFAULT NULL"),
                    ("voice_memes_count", "INT DEFAULT 0"),
                    ("quest_id", "VARCHAR(50) DEFAULT NULL"),
                    ("quest_progress", "INT DEFAULT 0"),
                    ("quest_target", "INT DEFAULT 0"),
                    ("quest_reward_coins", "INT DEFAULT 0"),
                    ("quest_reward_xp", "INT DEFAULT 0"),
                    ("quest_date", "DATE DEFAULT NULL"),
                    ("quests_completed", "INT DEFAULT 0"),
                    ("bj_wins", "INT DEFAULT 0"),
                    ("quiz_correct", "INT DEFAULT 0")
                ]
                
                for col_name, col_type in columns_to_add:
                    try:
                        await cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                    except Exception:
                        pass 
                
                # Таблица кастомного профиля
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS profile_settings (
                        user_id VARCHAR(25) PRIMARY KEY,
                        bg_color VARCHAR(15) DEFAULT '#2b2d31'
                    )
                ''')

                # Таблица достижений
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS user_achievements (
                        user_id VARCHAR(25),
                        achievement_id VARCHAR(50),
                        date_earned DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY(user_id, achievement_id),
                        FOREIGN KEY(user_id) REFERENCES users(user_id)
                    )
                ''')
                
                # Миграция из временной таблицы achievements в user_achievements
                try:
                    await cur.execute("INSERT IGNORE INTO user_achievements (user_id, achievement_id, date_earned) SELECT user_id, achievement_id, timestamp FROM achievements")
                except:
                    pass

    async def get_setting(self, key: str, default=None):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT `value` FROM global_settings WHERE `key` = %s", (key,))
                res = await cur.fetchone()
                return res['value'] if res else default

    async def set_setting(self, key: str, value: str):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("REPLACE INTO global_settings (`key`, `value`) VALUES (%s, %s)", (key, value))

    async def get_user(self, user_id: str):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                res = await cur.fetchone()
                if not res:
                    await cur.execute("INSERT INTO users (user_id) VALUES (%s)", (user_id,))
                    await cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                    res = await cur.fetchone()
                return res

    async def update_user(self, user_id: str, **kwargs):
        if not kwargs: return
        fields = ", ".join([f"{k} = %s" for k in kwargs.keys()])
        values = list(kwargs.values())
        values.append(user_id)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"UPDATE users SET {fields} WHERE user_id = %s", tuple(values))

    async def add_achievement(self, user_id: str, ach_id: str):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    # Попытаемся скопировать старые ачивки, если они были сохранены в ошибочную таблицу
                    try:
                        await cur.execute("INSERT IGNORE INTO user_achievements (user_id, achievement_id, date_earned) SELECT user_id, achievement_id, timestamp FROM achievements")
                    except: pass
                    
                    await cur.execute("INSERT INTO user_achievements (user_id, achievement_id) VALUES (%s, %s)", (user_id, ach_id))
                    return True
                except:
                    return False

    async def get_achievements(self, user_id: str):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT achievement_id FROM user_achievements WHERE user_id = %s", (user_id,))
                res = await cur.fetchall()
                return [row['achievement_id'] for row in res]

    async def get_leaderboard(self, category: str, limit: int = 10):
        order_by = "xp DESC"
        if category == "coins":
            order_by = "vibecoins DESC"
        elif category == "voice":
            order_by = "voice_time_seconds DESC"
        elif category == "streak":
            order_by = "streak DESC"
            
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT user_id, level, xp, vibecoins, streak, voice_time_seconds FROM users ORDER BY {order_by} LIMIT %s", (limit,))
                return await cur.fetchall()

    async def get_expired_boosts(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                from datetime import datetime
                await cur.execute("SELECT user_id FROM users WHERE xp_boost_until IS NOT NULL AND xp_boost_until < %s", (datetime.utcnow(),))
                return await cur.fetchall()

db = Database()
