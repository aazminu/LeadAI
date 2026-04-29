# backend/db/database.py

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase
from config import settings


# ─── Engine ────────────────────────────────────────────────────
# Single engine instance for the entire app.
# pool_pre_ping=True means it tests connections before using them
# — handles dropped connections gracefully.
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,        # logs all SQL when DEBUG=True
    pool_pre_ping=True,
    pool_size=10,               # max 10 concurrent DB connections
    max_overflow=20,            # 20 extra connections under load
)


# ─── Session Factory ───────────────────────────────────────────
# AsyncSessionLocal is a factory — call it to get a new session.
# expire_on_commit=False means objects stay usable after commit
# — important for async patterns.
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ─── Base Class ────────────────────────────────────────────────
# All database models inherit from this.
class Base(DeclarativeBase):
    pass


# ─── Dependency ────────────────────────────────────────────────
# FastAPI injects this into any route that needs DB access.
# The 'async with' ensures the session is always closed,
# even if an exception occurs mid-request.
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ─── Table Creation ────────────────────────────────────────────
# Called once on app startup in main.py.
# Creates all tables that don't exist yet — safe to run repeatedly.
async def create_tables():

    import db.models
    
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'leadstatus') THEN
                    ALTER TYPE leadstatus ADD VALUE IF NOT EXISTS 'queued';
                    ALTER TYPE leadstatus ADD VALUE IF NOT EXISTS 'disqualified';
                END IF;
            END $$;
            """
        )
        await conn.exec_driver_sql(
            """
            ALTER TABLE IF EXISTS leads
            ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0
            """
        )
        await conn.exec_driver_sql(
            """
            ALTER TABLE IF EXISTS leads
            ADD COLUMN IF NOT EXISTS last_error TEXT
            """
        )
        await conn.run_sync(Base.metadata.create_all)
