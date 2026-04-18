import asyncio
import os
from utils.db import db
from config import DB_HOST, DB_USER, DB_PASS, DB_NAME
import aiomysql

async def main():
    pool = await aiomysql.create_pool(
        host=DB_HOST,
        port=3306,
        user=DB_USER,
        password=DB_PASS,
        db=DB_NAME,
        autocommit=True,
        cursorclass=aiomysql.DictCursor
    )
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT COUNT(*) as c FROM achievements")
            res = await cur.fetchone()
            print(f"Total achievements in DB: {res['c']}")
            
            await cur.execute("SELECT * FROM achievements LIMIT 5")
            rows = await cur.fetchall()
            for r in rows:
                print(r)

asyncio.run(main())
