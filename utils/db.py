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
                # Таблица пользователей (Экономика и Уровни)
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id VARCHAR(25) PRIMARY KEY,
                        vibecoins INT DEFAULT 0,
                        xp INT DEFAULT 0,
                        level INT DEFAULT 0,
                        streak INT DEFAULT 0,
                        last_daily DATETIME DEFAULT NULL,
                        voice_time_seconds INT DEFAULT 0
                    )
                ''')
                
                # Таблица кастомного профиля (если цвет профиля изменен)
                await cur.execute('''
                    CREATE TABLE IF NOT EXISTS profile_settings (
                        user_id VARCHAR(25) PRIMARY KEY,
                        bg_color VARCHAR(10) DEFAULT '#2b2d31',
                        title VARCHAR(50) DEFAULT NULL,
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
                    return {"user_id": str(user_id), "vibecoins": 0, "xp": 0, "level": 0, "streak": 0, "last_daily": None, "voice_time_seconds": 0}
                return user
                
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

db = Database()
