import typing
from typing import TYPE_CHECKING, Optional, List
from typing_extensions import Annotated

import strawberry
from decimal import Decimal
from app.db.models import (
    MethodEnum,
    Port as DBPort,
    PortUser as DBPortUser,
    ServerUser as DBServerUser,
)
from strawberry.scalars import JSON
from sqlalchemy import select, or_, func, insert, update, delete
from sqlalchemy.orm import joinedload, Query
from app.utils.selection import get_selections
from strawberry.types import Info
from strawberry.types.nodes import Selection
from .utils import PaginationWindow

if TYPE_CHECKING:
    from .port_forward import PortForwardRule
    from .server import Server
    from .user import User


count_cache: typing.Dict[int, int] = {}


@strawberry.type
class Port:
    id: int
    external_num: Optional[int]
    num: int
    server_id: int
    config: JSON
    notes: Optional[str]
    is_active: bool

    server: Annotated["Server", strawberry.lazy(".server")]
    users: typing.List[Annotated["User", strawberry.lazy(".user")]]
    allowed_users: typing.List[Annotated["PortUser", strawberry.lazy(".port")]]
    forward_rule: Optional[
        Annotated["PortForwardRule", strawberry.lazy(".port_forward")]
    ]
    usage: Optional["PortUsage"]

    @staticmethod
    async def get_rule_options(info: Info, port_id: int) -> List[str]:
        async_db = info.context["request"].state.async_db

        stmt = (
            select(DBPort)
            .where(DBPort.id == port_id)
            .options(joinedload(DBPort.server))
        )
        result = await async_db.execute(stmt)
        port = result.scalars().unique().first()
        return [
            m.value
            for m in MethodEnum
            if not port.server.config.get(f"{m.value}_disabled", False)
            and not port.config.get(f"{m.value}_disabled", False)
        ]

    @staticmethod
    def set_options(stmt: Query, selections: List[Selection]) -> Query:
        if selection := get_selections(selections, "server"):
            options = joinedload(DBPort.server)
            stmt = stmt.options(options)
        if selection := get_selections(selections, "users"):
            options = joinedload(DBPort.users)
            stmt = stmt.options(options)
        if selection := get_selections(selections, "allowedUsers"):
            options = joinedload(DBPort.allowed_users)
            if selection := get_selections(selection.selections, "user"):
                options = options.joinedload(DBPortUser.user)
            stmt = stmt.options(options)
        if selection := get_selections(selections, "forwardRule"):
            options = joinedload(DBPort.forward_rule)
            stmt = stmt.options(options)
        if selection := get_selections(selections, "usage"):
            options = joinedload(DBPort.usage)
            stmt = stmt.options(options)
        return stmt

    @staticmethod
    async def get_ports(info: Info, order_by: str = "num") -> List["Port"]:
        async_db = info.context["request"].state.async_db
        stmt = Port.set_options(
            select(DBPort).order_by(order_by),
            get_selections(info.selected_fields, info.field_name).selections,
        )
        result = await async_db.execute(stmt)
        return result.scalars().unique().all()

    @staticmethod
    async def get_paginated_ports(
        info: Info,
        order_by: str = "num",
        server_id: Optional[int] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> PaginationWindow["Port"]:
        async_db = info.context["request"].state.async_db
        # user = info.context["request"].state.user

        stmt = Port.set_options(
            select(DBPort)
            .order_by(order_by)
            .options(joinedload(DBPort.allowed_users))
            .where(DBPort.is_active == True),
            get_selections(
                info.selected_fields, f"{info.field_name}.items"
            ).selections,
        )
        if server_id:
            stmt = stmt.where(DBPort.server_id == server_id)
        stmt = stmt.offset(offset).limit(limit)

        result = await async_db.execute(stmt)
        return PaginationWindow(
            items=result.scalars().unique().all(),
            count=await Port.get_port_count(info, server_id=server_id),
        )

    @staticmethod
    async def get_port(
        info: Info,
        id: Optional[int] = None,
        server_id: Optional[int] = None,
        num: Optional[int] = None,
    ) -> Optional["Port"]:
        async_db = info.context["request"].state.async_db

        stmt = Port.set_options(
            select(DBPort),
            get_selections(
                info.selected_fields, f"{info.field_name}"
            ).selections,
        )
        if id:
            stmt = stmt.where(DBPort.id == id)
        if server_id:
            stmt = stmt.where(DBPort.server_id == server_id)
        if num:
            stmt = stmt.where(
                or_(DBPort.num == num, DBPort.external_num == num)
            )
        result = await async_db.execute(stmt)
        return result.scalars().unique().first()

    @staticmethod
    async def get_port_count(
        info: Info, server_id: Optional[int] = None
    ) -> int:
        async_db = info.context["request"].state.async_db
        user = info.context["request"].state.user

        if (user.id, server_id) not in count_cache:
            stmt = select(func.count(DBPort.id, distinct=True))
            if not user.is_superuser:
                conditions = [
                    DBPort.id.in_(
                        select(DBPortUser.port_id).where(
                            DBPortUser.user_id == user.id
                        )
                    )
                ]
                if user.is_ops:
                    conditions.append(
                        DBPort.server_id.in_(
                            select(DBServerUser.server_id).where(
                                DBServerUser.user_id == user.id
                            )
                        )
                    )
                stmt = stmt.where(or_(*conditions))
            if server_id:
                stmt = stmt.where(DBPort.server_id == server_id)
            stmt = stmt.where(DBPort.is_active == True)

            result = await async_db.execute(stmt)
            count_cache[(user.id, server_id)] = result.scalar()
        return count_cache[(user.id, server_id)]

    @staticmethod
    async def add_port(
        info: Info,
        server_id: int,
        num: int,
        external_num: Optional[int] = None,
        config: Optional[JSON] = None,
        notes: Optional[str] = None,
    ) -> bool:
        async_db = info.context["request"].state.async_db

        stmt = insert(DBPort).values(
            server_id=server_id,
            num=num,
            external_num=external_num,
            config=config,
            notes=notes,
        )
        result = await async_db.execute(stmt)
        await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def update_port(
        info: Info,
        id: int,
        server_id: Optional[int] = None,
        num: Optional[int] = None,
        external_num: Optional[int] = None,
        config: Optional[JSON] = None,
        notes: Optional[str] = None,
    ) -> bool:
        async_db = info.context["request"].state.async_db

        stmt = update(DBPort).where(DBPort.id == id)
        if server_id:
            stmt = stmt.values(server_id=server_id)
        if num:
            stmt = stmt.values(num=num)
        if external_num:
            stmt = stmt.values(external_num=external_num)
        if config:
            stmt = stmt.values(config=config)
        if notes:
            stmt = stmt.values(notes=notes)
        result = await async_db.execute(stmt)
        await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def delete_port(info: Info, id: int) -> bool:
        async_db = info.context["request"].state.async_db

        stmt = delete(DBPort).where(DBPort.id == id)
        result = await async_db.execute(stmt)
        await async_db.commit()
        return result.rowcount > 0


@strawberry.type
class PortUser:
    id: int
    port_id: int
    user_id: int
    config: JSON

    user: Annotated["User", strawberry.lazy(".user")]
    port: Annotated["Port", strawberry.lazy(".port")]

    @staticmethod
    async def add_port_user(
        info: Info,
        port_id: int,
        user_id: int,
        config: Optional[JSON] = None,
    ) -> bool:
        async_db = info.context["request"].state.async_db

        stmt = insert(DBPortUser).values(
            port_id=port_id, user_id=user_id, config=config
        )
        result = await async_db.execute(stmt)
        await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def delete_port_user(info: Info, port_id: int, user_id: int) -> bool:
        async_db = info.context["request"].state.async_db

        stmt = delete(DBPortUser).where(
            DBPortUser.port_id == port_id, DBPortUser.user_id == user_id
        )
        result = await async_db.execute(stmt)
        await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def update_port_user(
        info: Info,
        port_id: int,
        user_id: int,
        config: Optional[JSON] = None,
    ) -> bool:
        async_db = info.context["request"].state.async_db

        stmt = update(DBPortUser).where(
            DBPortUser.port_id == port_id, DBPortUser.user_id == user_id
        )
        if config:
            stmt = stmt.values(config=config)
        result = await async_db.execute(stmt)
        await async_db.commit()
        return result.rowcount > 0


@strawberry.type
class PortUsage:
    id: int
    port_id: int
    download: Decimal
    upload: Decimal
    download_accumulate: Decimal
    upload_accumulate: Decimal
    download_checkpoint: int
    upload_checkpoint: int

    port: Annotated["Port", strawberry.lazy(".port")]
