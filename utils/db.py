import aiomysql
import logging
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        try:
            # We assume the database `mriamys_bot` exists or we create it.
            # Due to limitations on standard users, the DB should be pre-created by the server admin.
            self.pool = await aiomysql.create_pool(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASS,
                db=DB_NAME,
                autocommit=True,
                cursorclass=aiomysql.DictCursor
            )
            logging.info("Connected to MySQL Database.")
            await self.init_tables()
        except Exception as e:
            logging.error(f"Failed to connect to MySQL: {e}")
            logging.error("Please check your DB_HOST, DB_USER, DB_PASS, and DB_NAME in .env")

    async def init_tables(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Таблица пользователей (Экономика и Уровни + Статистика для ачивок)
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id VARCHAR(25) PRIMARY KEY,
                        vibecoins INT DEFAULT 0,
                        xp INT DEFAULT 0,
                        level INT DEFAULT 0,
                        streak INT DEFAULT 0,
                        last_daily DATETIME DEFAULT NULL,
                        voice_time_seconds INT DEFAULT 0,
                        msg_count INT DEFAULT 0,
                        shop_spent INT DEFAULT 0,
                        nick_changes INT DEFAULT 0,
                        casino_spent INT DEFAULT 0,
                        casino_wins INT DEFAULT 0,
                        xp_boost_until DATETIME DEFAULT NULL,
                        cases_opened INT DEFAULT 0,
                        duels_won INT DEFAULT 0,
                        memes_ordered INT DEFAULT 0,
                        voice_memes_until DATETIME DEFAULT NULL,
                        voice_memes_count INT DEFAULT 0
                    )
                ''')
                
                # Добавляем колонки в существующие таблицы по одной
                columns_to_add = [
                    ("msg_count", "INT DEFAULT 0"),
                    ("shop_spent", "INT DEFAULT 0"),
                    ("nick_changes", "INT DEFAULT 0"),
                    ("casino_spent", "INT DEFAULT 0"),
                    ("casino_wins", "INT DEFAULT 0"),
                    ("xp_boost_until", "DATETIME DEFAULT NULL"),
                    ("cases_opened", "INT DEFAULT 0"),
                    ("duels_won", "INT DEFAULT 0"),
                    ("memes_ordered", "INT DEFAULT 0"),
                    ("voice_memes_until", "DATETIME DEFAULT NULL"),
                    ("voice_memes_count", "INT DEFAULT 0")
                ]
                
                for col_name, col_type in columns_to_add:
                    try:
                        await cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                    except Exception:
                        pass # Колонка уже существует
                
                # Таблица кастомного профиля
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS profile_settings (
                        user_id VARCHAR(25) PRIMARY KEY,
                        bg_color VARCHAR(10) DEFAULT '#2b2d31',
                        title VARCHAR(50) DEFAULT NULL,
                        FOREIGN KEY(user_id) REFERENCES users(user_id)
                    )
                ''')
                
                # Таблица связи юзер - ачивки
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS user_achievements (
                        user_id VARCHAR(25),
                        achievement_id VARCHAR(50),
                        date_earned DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY(user_id, achievement_id),
                        FOREIGN KEY(user_id) REFERENCES users(user_id)
                    )
                ''')
        logging.info("Database tables initialized.")

    async def get_user(self, user_id: str):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM users WHERE user_id = %s", (str(user_id),))
                user = await cur.fetchone()
                if not user:
                    await cur.execute("INSERT INTO users (user_id) VALUES (%s)", (str(user_id),))
                    return {"user_id": str(user_id), "vibecoins": 0, "xp": 0, "level": 0, "streak": 0, "last_daily": None, "voice_time_seconds": 0, "msg_count": 0, "shop_spent": 0, "nick_changes": 0, "casino_spent": 0, "casino_wins": 0, "xp_boost_until": None, "cases_opened": 0, "duels_won": 0, "memes_ordered": 0, "voice_memes_until": None, "voice_memes_count": 0}
                return user
                
    async def get_achievements(self, user_id: str):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT achievement_id FROM user_achievements WHERE user_id = %s", (str(user_id),))
                rows = await cur.fetchall()
                return [r['achievement_id'] for r in rows] if rows else []

    async def add_achievement(self, user_id: str, achievement_id: str) -> bool:
        """Возвращает True если ачивка новая и добавлена, False если уже была."""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute("INSERT INTO user_achievements (user_id, achievement_id) VALUES (%s, %s)", (str(user_id), achievement_id))
                    return True
                except Exception:
                    # Duplicate entry
                    return False
                
    async def update_user(self, user_id: str, **kwargs):
        if not kwargs: return
        
        set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
        values = list(kwargs.values())
        values.append(str(user_id))
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # В случае, если юзера еще нет – обеспечим его создание:
                await self.get_user(str(user_id)) 
                
                query = f"UPDATE users SET {set_clause} WHERE user_id = %s"
                await cur.execute(query, values)

    async def get_leaderboard(self, category: str, limit: int = 10):
        order_by = "level DESC, xp DESC"
        if category == "coins":
            order_by = "vibecoins DESC"
        elif category == "voice":
            order_by = "voice_time_seconds DESC"
        elif category == "streak":
            order_by = "streak DESC"
            
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT * FROM users ORDER BY {order_by} LIMIT %s", (limit,))
                return await cur.fetchall()

    async def get_active_voice_memes(self):
        """Возвращает список пользователей, у которых активен аудио-троллинг."""
        from datetime import datetime
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM users WHERE voice_memes_until > %s AND voice_memes_count < 10", (datetime.utcnow(),))
                return await cur.fetchall()

db = Database()
