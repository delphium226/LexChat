import asyncpg
from config import settings
import logging

logger = logging.getLogger("lexchat.db")

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        try:
            self.pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=1,
                max_size=10
            )
            logger.info("Connected to database")
            await self.init_db()
        except Exception as e:
            logger.error(f"DB Connection failed: {e}")
            raise e

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            logger.info("Disconnected from database")

    async def fetch_one(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetch_all(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
            
    async def init_db(self):
        # Base tables are assumed to exist from Node app, but we can ensure them or specific columns
        pass

db = Database()
