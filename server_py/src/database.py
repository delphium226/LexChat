import logging
from typing import AsyncGenerator

from passlib.hash import bcrypt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .config import settings
from .models import Base, User

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
    logger.info("Initialising database...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
            logger.info("Default admin user created.")
        else:
            logger.info("Admin user already exists.")

    logger.info("Database initialised successfully.")
