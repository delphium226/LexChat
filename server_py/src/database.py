import logging
from typing import AsyncGenerator

from passlib.hash import bcrypt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .config import settings
from .models import AppSetting, Base, User

logger = logging.getLogger("app")

# Use asyncpg driver
DB_URL = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    DB_URL,
    echo=False,
    pool_size=settings.db_max_connections,
    max_overflow=5,
)

async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def init_db() -> None:
    """Create tables and seed default admin user."""
    logger.info("[Database] Initialising...")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Migrate existing tables — add columns that may not exist yet
        migration_statements = [
            "ALTER TABLE chats ADD COLUMN IF NOT EXISTS provider VARCHAR(50)",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS model VARCHAR(255)",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS provider VARCHAR(50)",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS cost_usd FLOAT",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS total_cost_usd FLOAT NOT NULL DEFAULT 0.0",
        ]
        async with engine.begin() as conn:
            for stmt in migration_statements:
                await conn.execute(text(stmt))
        logger.info("[Database] Column migrations applied.")

        # Apply indexes to existing tables (create_all only indexes new tables)
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_chats_user_created ON chats (user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_chats_created_at ON chats (created_at)",
            "CREATE INDEX IF NOT EXISTS idx_messages_chat_created ON messages (chat_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages (created_at)",
            "CREATE INDEX IF NOT EXISTS idx_messages_rated ON messages (chat_id, created_at) WHERE rating IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_messages_content_fts ON messages USING GIN (to_tsvector('english', content))",
            "CREATE INDEX IF NOT EXISTS idx_health_service_checked ON service_health_logs (service_name, checked_at)",
            "CREATE INDEX IF NOT EXISTS idx_request_timings_created_at ON request_timings (created_at)",
        ]
        async with engine.begin() as conn:
            for stmt in index_statements:
                await conn.execute(text(stmt))
        logger.info("[Database] Indexes applied.")

        # Seed default admin user
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.username == "admin")
            )
            admin = result.scalar_one_or_none()

            if admin is None:
                hashed = bcrypt.using(rounds=10).hash("admin")
                admin_user = User(
                    username="admin",
                    password_hash=hashed,
                    role="admin",
                )
                session.add(admin_user)
                await session.commit()
                logger.info("[Database] Default admin user created.")
            else:
                logger.info("[Database] Admin user already exists.")

        # Seed default active_provider setting
        async with async_session_maker() as session:
            result = await session.execute(
                select(AppSetting).where(AppSetting.key == "active_provider")
            )
            if result.scalar_one_or_none() is None:
                session.add(AppSetting(key="active_provider", value="ollama"))
                await session.commit()
                logger.info("[Database] Default active_provider seeded.")

        logger.info("[Database] Initialised successfully.")
    except Exception as e:
        logger.error(f"[Database] Initialisation failed: {e}. The server will start, but database-dependent features will fail.")
