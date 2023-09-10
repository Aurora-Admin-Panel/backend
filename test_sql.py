import asyncio

from app.db.models import Port as DBPort
from app.db.models import PortUser as DBPortUser
from app.db.models import Server as DBServer
from app.db.models import ServerUser as DBServerUser
from app.db.models import User as DBUser
from app.db.models import File as DBfile
from sqlalchemy import Column, MetaData, String, Table, select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import joinedload, sessionmaker


async def async_main() -> None:
    engine = create_async_engine(
        "postgresql+asyncpg://aurora:AuroraAdminPanel321@localhost:5432/aurora",
        echo=True,
    )
    # async_session = async_session(engine, expire_on_commit=False)
    AsyncSessionMaker = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionMaker() as session:
        stmt = (
            delete(DBfile).where(DBfile.id == 4).returning(DBfile.storage_path)
        )

        result = await session.execute(stmt)
        print(result)
        print(result.scalars().one_or_none())
        await session.commit()

    # for AsyncEngine created in function scope, close and
    # clean-up pooled connections
    await engine.dispose()


asyncio.run(async_main())
