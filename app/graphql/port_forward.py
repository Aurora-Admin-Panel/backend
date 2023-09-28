from typing import TYPE_CHECKING, Optional, List

import strawberry
from strawberry.types import Info
from app.db.models import (
    MethodEnum,
    PortForwardRule as DBPortForwardRule,
    Port as DBPort,
)
from app.db.async_session import async_db_session
from sqlalchemy import select, insert, update, delete
from sqlalchemy.orm import joinedload
from strawberry.scalars import JSON
from typing_extensions import Annotated

if TYPE_CHECKING:
    from .port import Port


@strawberry.type
class PortForwardRule:
    id: int
    port_id: int
    config: JSON
    method: strawberry.enum(MethodEnum)
    status: str
    is_active: bool

    port: Annotated["Port", strawberry.lazy(".port")]


    @staticmethod
    async def get_port_forward_rule(
        info: Info, port_id: int
    ) -> "PortForwardRule":
        stmt = select(DBPortForwardRule).where(
            DBPortForwardRule.port_id == port_id
        )

        with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            return result.scalars().unique().first()

    @staticmethod
    async def create_port_forward_rule(
        info: Info, port_id: int, config: JSON, method: MethodEnum
    ) -> bool:
        stmt = insert(DBPortForwardRule).values(
            port_id=port_id, config=config, method=method
        )

        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def update_port_forward_rule(
        info: Info,
        id: int,
        port_id: Optional[int] = None,
        config: Optional[JSON] = None,
        method: Optional[MethodEnum] = None,
    ) -> bool:
        stmt = update(DBPortForwardRule).where(DBPortForwardRule.id == id)
        if port_id:
            stmt = stmt.values(port_id=port_id)
        if config:
            stmt = stmt.values(config=config)
        if method:
            stmt = stmt.values(method=method)
        
        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def delete_port_forward_rule(info: Info, id: int) -> bool:
        stmt = delete(DBPortForwardRule).where(DBPortForwardRule.id == id)

        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            await async_db.commit()
        return result.rowcount > 0
