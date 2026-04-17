from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Initialize engine and session maker
try:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
except Exception as e:
    logger.warning(f"Failed to initialize database engine: {e}. Database operations may not be available.")
    engine = None
    AsyncSessionLocal = None


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    if AsyncSessionLocal is None:
        raise RuntimeError("Database session maker not initialized")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    if engine is None:
        logger.warning("Database engine not initialized, skipping database initialization")
        return
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
