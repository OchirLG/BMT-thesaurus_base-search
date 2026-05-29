import asyncpg
from pgvector.asyncpg import register_vector
from .config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool = None

    
    async def _init_connection(self, conn):
        await register_vector(conn)

 
    async def connect(self):
        try:
            self.pool = await asyncpg.create_pool(
                host=settings.db_host,
                port=settings.db_port,
                database=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
                min_size=5,
                max_size=20,
                command_timeout=120,
                timeout=120,
                init=self._init_connection
            )
            logger.info("Database connected successfully")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise


    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            logger.info("Database disconnected")

    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

db = Database()