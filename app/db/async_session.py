from contextlib import asynccontextmanager

from fastapi import Request
from app.core import config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


@asynccontextmanager
async def async_db_session():
    engine = create_async_engine(
        config.SQLALCHEMY_ASYNC_DATABASE_URI,
        echo=True,
    )
    AsyncSessionMaker = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with AsyncSessionMaker() as session:
        try:
            yield session
        finally:
            await engine.dispose()


def get_async_db(request: Request):
    return request.state.async_db
