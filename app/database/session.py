from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import settings
from app.database.models import Base

# Import campus + auth models so Base.metadata.create_all picks them up
import app.auth.models  # noqa: F401
import app.campus.models  # noqa: F401

logger = logging.getLogger(__name__)

async_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_MIN_SIZE,
    max_overflow=settings.DB_POOL_MAX_SIZE - settings.DB_POOL_MIN_SIZE,
    echo=False,
    future=True,
)

async_session = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Initialize database schema and extension for agent_memory + campus."""
    try:
        async with async_engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS agent_memory;"))
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS campus;"))
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_agent_experience_context_embedding "
                "ON agent_memory.agent_experience_logs "
                "USING ivfflat (context_embedding vector_cosine_ops) WITH (lists = 100);"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_environment_snapshots_embedding "
                "ON agent_memory.environment_snapshots "
                "USING ivfflat (environment_embedding vector_cosine_ops) WITH (lists = 100);"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_agent_decision_logs_embedding "
                "ON agent_memory.agent_decision_logs "
                "USING ivfflat (response_embedding vector_cosine_ops) WITH (lists = 100);"
            ))
        logger.info("Successfully initialized pgvector database schema 'agent_memory' + 'campus'")
    except Exception as e:
        logger.warning("Could not initialize database schemas: %s", e)


@asynccontextmanager
async def get_async_db() -> AsyncIterator[AsyncSession]:
    """Dependency helper for acquiring AsyncSession."""
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

