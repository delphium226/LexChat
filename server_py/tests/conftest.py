import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from passlib.hash import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.database import get_db
from src.dependencies import create_access_token
from src.main import app
from src.models import Base, User

# Use the same DB URL (in CI you'd point to a test-specific DB)
TEST_DB_URL = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
)

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """Create all tables once for the test session."""
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
