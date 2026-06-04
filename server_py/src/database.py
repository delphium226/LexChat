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
        # matters/matter_notes tables must be created before matter_id FK is added to chats.
        # For fresh installs, create_all handles table creation in dependency order.
        # For existing databases, we create the new tables explicitly first.
        migration_statements = [
            # New tables (safe to run on existing DBs via IF NOT EXISTS)
            """CREATE TABLE IF NOT EXISTS matters (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                status VARCHAR(50) NOT NULL DEFAULT 'open',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            """CREATE TABLE IF NOT EXISTS matter_notes (
                id SERIAL PRIMARY KEY,
                matter_id INTEGER NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            # Existing table column additions
            "ALTER TABLE chats ADD COLUMN IF NOT EXISTS provider VARCHAR(50)",
            "ALTER TABLE chats ADD COLUMN IF NOT EXISTS matter_id INTEGER REFERENCES matters(id) ON DELETE SET NULL",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS model VARCHAR(255)",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS provider VARCHAR(50)",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS cost_usd FLOAT",
            "ALTER TABLE request_timings ADD COLUMN IF NOT EXISTS total_cost_usd FLOAT NOT NULL DEFAULT 0.0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS research_mode VARCHAR(50) NOT NULL DEFAULT 'legislation_only'",
            "ALTER TABLE matters ADD COLUMN IF NOT EXISTS jurisdiction VARCHAR(100)",
            "ALTER TABLE matters ADD COLUMN IF NOT EXISTS legislation_type VARCHAR(100)",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS sources JSONB",
            """CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                filename VARCHAR(255) NOT NULL,
                content_text TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            "ALTER TABLE product_feedback ALTER COLUMN message DROP NOT NULL",
            "ALTER TABLE product_feedback ADD COLUMN IF NOT EXISTS time_saved_hours FLOAT",
            "ALTER TABLE product_feedback ADD COLUMN IF NOT EXISTS time_without_aila_hours FLOAT",
            "ALTER TABLE product_feedback ADD COLUMN IF NOT EXISTS research_success VARCHAR(50)",
            "ALTER TABLE product_feedback ADD COLUMN IF NOT EXISTS confidence INTEGER",
            "ALTER TABLE product_feedback ADD COLUMN IF NOT EXISTS verification_hours FLOAT",
            "ALTER TABLE product_feedback ADD COLUMN IF NOT EXISTS usability INTEGER",
            """CREATE TABLE IF NOT EXISTS activity_log (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(20) NOT NULL,
                username VARCHAR(255) NOT NULL,
                description TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            """CREATE TABLE IF NOT EXISTS peer_bots (
                id SERIAL PRIMARY KEY,
                peer_id VARCHAR(64) NOT NULL UNIQUE,
                name VARCHAR(128) NOT NULL,
                base_url VARCHAR(256) NOT NULL,
                api_key VARCHAR(256),
                description TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )""",
            "ALTER TABLE peer_bots ADD COLUMN IF NOT EXISTS name VARCHAR(128) NOT NULL DEFAULT ''",
        ]
        async with engine.begin() as conn:
            for stmt in migration_statements:
                await conn.execute(text(stmt))
        logger.info("[Database] Column migrations applied.")

        # Apply indexes to existing tables (create_all only indexes new tables)
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_chats_user_created ON chats (user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_chats_created_at ON chats (created_at)",
            "CREATE INDEX IF NOT EXISTS idx_chats_matter ON chats (matter_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_chat_created ON messages (chat_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages (created_at)",
            "CREATE INDEX IF NOT EXISTS idx_messages_rated ON messages (chat_id, created_at) WHERE rating IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_messages_content_fts ON messages USING GIN (to_tsvector('english', content))",
            "CREATE INDEX IF NOT EXISTS idx_health_service_checked ON service_health_logs (service_name, checked_at)",
            "CREATE INDEX IF NOT EXISTS idx_request_timings_created_at ON request_timings (created_at)",
            "CREATE INDEX IF NOT EXISTS idx_matters_user_created ON matters (user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_matter_notes_matter ON matter_notes (matter_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_documents_chat ON documents (chat_id)",
            "CREATE INDEX IF NOT EXISTS idx_activity_log_created_at ON activity_log (created_at)",
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
