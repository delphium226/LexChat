import os

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from passlib.hash import bcrypt
from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# D4: the test suite gets its OWN database. The old conftest pointed at the
# dev `lexchat` DB and dropped every table at session end, wiping local chats
# and provider settings on each pytest run.
#
# Resolution order: TEST_DATABASE_URL env var, else the dev DATABASE_URL
# (env var / .env / default) with `_test` appended to the database name.
# The resolved URL is exported as DATABASE_URL *before any src import* —
# src.database builds its engine (and async_session_maker, used directly by
# app code such as /api/chat) from settings.database_url at import time, and
# real env vars take precedence over .env in pydantic-settings — so the whole
# app under test runs against the test DB, not just the get_db override.
# ---------------------------------------------------------------------------

def _dev_db_url() -> str:
    from dotenv import dotenv_values
    return (
        os.environ.get("DATABASE_URL")
        or dotenv_values(".env").get("DATABASE_URL")
        or "postgresql://lexuser:lexpassword@localhost:5432/lexchat"
    )


_DEV_URL = make_url(_dev_db_url())
_explicit = os.environ.get("TEST_DATABASE_URL")
_TEST_URL = (
    make_url(_explicit) if _explicit
    else _DEV_URL.set(database=f"{_DEV_URL.database}_test")
)

if (_TEST_URL.host, _TEST_URL.port, _TEST_URL.database) == (
    _DEV_URL.host, _DEV_URL.port, _DEV_URL.database
):
    pytest.exit(
        f"Refusing to run tests against the dev database "
        f"'{_DEV_URL.database}' — set TEST_DATABASE_URL to a dedicated test DB.",
        returncode=1,
    )

os.environ["DATABASE_URL"] = _TEST_URL.render_as_string(hide_password=False)

from src.config import settings  # noqa: E402
from src.database import get_db  # noqa: E402
from src.dependencies import create_access_token  # noqa: E402
from src.main import app  # noqa: E402
from src.models import Base, User  # noqa: E402

# If this trips, the env override above no longer wins over .env — every test
# would silently run (and drop tables!) against the dev DB again.
assert settings.database_url == os.environ["DATABASE_URL"], (
    "settings.database_url did not pick up the test-DB override"
)

TEST_DB_URL = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
)

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

# Written on first initialisation of the test DB; its absence in a DB that
# already contains tables means we are pointed at somebody's real data.
_MARKER_TABLE = "test_db_marker"


async def _ensure_test_database_exists():
    """CREATE DATABASE on demand (connects to the 'postgres' maintenance DB)."""
    admin_dsn = _TEST_URL.set(database="postgres").render_as_string(
        hide_password=False
    )
    conn = await asyncpg.connect(dsn=admin_dsn)
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", _TEST_URL.database
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{_TEST_URL.database}"')
    finally:
        await conn.close()


async def _guard_against_non_test_data():
    """Abort if the target DB has tables but was never marked as a test DB."""
    async with test_engine.begin() as conn:
        marker = await conn.scalar(
            text(f"SELECT to_regclass('public.{_MARKER_TABLE}')")
        )
        other_tables = await conn.scalar(text(
            "SELECT COUNT(*) FROM information_schema.tables "
            f"WHERE table_schema = 'public' AND table_name <> '{_MARKER_TABLE}'"
        ))
        if other_tables and marker is None:
            pytest.exit(
                f"Refusing to run: database '{_TEST_URL.database}' contains "
                f"{other_tables} tables but no '{_MARKER_TABLE}' marker — it "
                "looks like a live database, and the test teardown DROPS ALL "
                "TABLES. Point TEST_DATABASE_URL at a dedicated test DB.",
                returncode=1,
            )
        await conn.execute(text(
            f"CREATE TABLE IF NOT EXISTS {_MARKER_TABLE} "
            "(created_at TIMESTAMP DEFAULT NOW())"
        ))


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """Create the test DB if needed, then all tables, once per session."""
    await _ensure_test_database_exists()
    await _guard_against_non_test_data()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """Empty every table before each test.

    Tables are created once per session (setup_db) and the app commits real
    transactions through the shared session, so without this the function-scoped
    seed_admin/seed_user fixtures collide on the unique username column on the
    second test that uses them (and on rows left behind by a crashed prior run).
    """
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield


@pytest_asyncio.fixture
async def db_session():
    """Provide a DB session for each test."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """Async test client with DB dependency override."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_admin(db_session: AsyncSession) -> User:
    """Create an admin user in the test DB."""
    admin = User(
        username="admin",
        password_hash=bcrypt.using(rounds=4).hash("admin"),
        role="admin",
        email="admin@test.com",
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest_asyncio.fixture
async def seed_user(db_session: AsyncSession) -> User:
    """Create a regular user in the test DB."""
    user = User(
        username="testuser",
        password_hash=bcrypt.using(rounds=4).hash("testpassword"),
        role="user",
        email="test@test.com",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_token() -> str:
    """A valid JWT for a fictitious user — DB-free.

    `get_current_user` only decodes the token; it never loads the user row, so
    endpoints gated solely on authentication (not on a DB-resolved user) can be
    exercised without a live Postgres.
    """
    return create_access_token(data={"sub": "testuser", "id": 1, "role": "user"})


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Authorization header carrying the DB-free auth token."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_token(seed_admin: User) -> str:
    """JWT token for the admin user."""
    return create_access_token(
        data={"sub": seed_admin.username, "id": seed_admin.id, "role": seed_admin.role}
    )


@pytest.fixture
def user_token(seed_user: User) -> str:
    """JWT token for a regular user."""
    return create_access_token(
        data={"sub": seed_user.username, "id": seed_user.id, "role": seed_user.role}
    )
