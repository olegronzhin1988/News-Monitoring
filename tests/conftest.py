# conftest.py — shared pytest fixtures for the whole test suite.
#
# Key design decisions:
# - A separate Postgres instance (docker-compose.test.yml) is used instead of SQLite,
#   because our models rely on PostgreSQL-specific types (ARRAY, native UUID, JSON)
#   that SQLite does not support the same way.
# - Each test function gets a clean set of tables: we drop and recreate the schema
#   around every test via a function-scoped fixture, so tests never see leftover
#   data from a previous test.
# - All external services (NewsAPI, Groq, OpenRouter, Telegram) are mocked in the
#   relevant test modules — the test DB is the only real I/O happening here.

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Make sure the test DB is used everywhere before any app module is imported.
# This must happen before "from app..." imports below, since app.core.config
# reads environment variables at import time via pydantic-settings.
os.environ["POSTGRES_HOST"] = os.environ.get("TEST_POSTGRES_HOST", "localhost")
os.environ["POSTGRES_PORT"] = os.environ.get("TEST_POSTGRES_PORT", "5433")
os.environ["POSTGRES_DB"] = "news_monitoring_test"

# Ensure the project root is importable when pytest is run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.models import Base  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.core.database import get_db  # noqa: E402


@pytest_asyncio.fixture
async def test_engine():
    """
    Function-scoped async engine pointing at the isolated test database.
    Deliberately NOT session-scoped: pytest-asyncio creates a fresh event
    loop per test function by default, and asyncpg connections are bound to
    the loop they were created on (the same issue we hit with Celery on
    Windows — see README's "asyncpg + Celery + asyncio.run()" note). A
    session-scoped engine would end up attached to a loop from an earlier
    test and fail with "Future attached to a different loop" on later tests.
    """
    engine = create_async_engine(settings.DATABASE_URL)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    """
    Recreates all tables before each test and tears them down after.
    This guarantees every test starts from a known-empty schema, regardless
    of what previous tests inserted.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    yield session_factory

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(test_session_factory):
    """A single AsyncSession for tests that talk to the DB directly."""
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_session_factory):
    """
    An httpx.AsyncClient wired to the FastAPI app, with the real get_db
    dependency overridden to use the test database session factory instead
    of the production one.
    """

    async def _override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
