from contextlib import asynccontextmanager

from fastapi import Request
from app.core import config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    config.SQLALCHEMY_ASYNC_DATABASE_URI,
    echo=True,
)
AsyncSessionMaker = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

@asynccontextmanager
async def async_db_session():
    async with AsyncSessionMaker() as session:
        try:
            yield session
        finally:
            await session.close()

async def dispose_engine():
    await engine.dispose()
