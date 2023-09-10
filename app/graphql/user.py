import typing
from typing import TYPE_CHECKING, List, Optional

import strawberry
from fastapi import Request
from app.core.security import get_password_hash
from app.db.models import Port as DBPort
from app.db.models import PortUser as DBPortUser
from app.db.models import Server as DBServer
from app.db.models import ServerUser as DBServerUser
from app.db.models import User as DBUser
from app.utils.selection import get_selections
from sqlalchemy import func, insert, inspect, select, update, delete
from sqlalchemy.orm import Query, joinedload
from strawberry.field import StrawberryField
from strawberry.types import Info
from strawberry.types.nodes import Selection
from typing_extensions import Annotated

from .auth import IsAdmin, IsAuthenticated, IsSuperUser
from .utils import PaginationWindow

if TYPE_CHECKING:
    from .port import Port, PortUser
    from .server import Server, ServerUser


count_cache: typing.Dict[int, int] = {}


@strawberry.type
class User:
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    hashed_password: str
    is_active: bool
    is_ops: bool = strawberry.field(permission_classes=[IsSuperUser])
    is_superuser: bool = strawberry.field(permission_classes=[IsSuperUser])
    notes: str

    allowed_servers: typing.List[
        Annotated["ServerUser", strawberry.lazy(".server")]
    ]
    servers: typing.List[Annotated["Server", strawberry.lazy(".server")]]
    allowed_ports: typing.List[Annotated["PortUser", strawberry.lazy(".port")]]
    ports: typing.List[Annotated["Port", strawberry.lazy(".port")]]

    @staticmethod
    async def get_user_by_email(async_db, email: str) -> "DBUser":
        stmt = select(DBUser).where(DBUser.email == email)
        result = await async_db.execute(stmt)
        return result.scalars().unique().first()

    @staticmethod
    def set_options(stmt: Query, selections: List[Selection]) -> Query:
        if selection := get_selections(selections, "allowedServers"):
            options = joinedload(DBUser.allowed_servers)
            if selection := get_selections(selection.selections, "server"):
                options = options.joinedload(DBServerUser.server)
            stmt = stmt.options(options)

        if selection := get_selections(selections, "servers"):
            options = joinedload(DBUser.servers)
            stmt = stmt.options(options)

        if selection := get_selections(selections, "allowedPorts"):
            options = joinedload(DBUser.allowed_ports)
            if selection := get_selections(selection.selections, "port"):
                options = options.joinedload(DBPortUser.port)
                sub_options = []
                if get_selections(selection.selections, "server"):
                    sub_options.append(joinedload(DBPort.server))
                if get_selections(selection.selections, "usage"):
                    sub_options.append(joinedload(DBPort.usage))
                if get_selections(selection.selections, "forwardRule"):
                    sub_options.append(joinedload(DBPort.forward_rule))
                if sub_options:
                    options = options.options(*sub_options)
            stmt = stmt.options(options)

        if selection := get_selections(selections, "ports"):
            options = joinedload(DBUser.ports)
            if selection := get_selections(selection.selections, "server"):
                options = options.joinedload(DBPort.server)
            stmt = stmt.options(options)
        return stmt

    @staticmethod
    def get_stmt_with_options(info: Info, stmt: Query) -> Query:
        return User.set_options(
            stmt,
            get_selections(
                info.selected_fields, f"{info.field_name}"
            ).selections,
        )

    @staticmethod
    async def get_users(
        info: Info, order_by: Optional[str] = "email"
    ) -> List["User"]:
        async_db = info.context["request"].state.async_db

        stmt = User.get_stmt_with_options(
            info, select(DBUser).order_by(f"{order_by}")
        )

        result = await async_db.execute(stmt)
        return result.scalars().unique().all()

    @staticmethod
    async def get_paginated_users(
        info: Info,
        order_by: Optional[str] = "email",
        email: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> PaginationWindow["User"]:
        async_db = info.context["request"].state.async_db

        stmt = User.set_options(
            select(DBUser).order_by(f"{order_by}"),
            get_selections(
                info.selected_fields, f"{info.field_name}.items"
            ).selections,
        )
        if email:
            stmt = stmt.where(DBUser.email.ilike(f"%{email}%"))
        stmt = stmt.limit(limit).offset(offset)

        result = await async_db.execute(stmt)
        return PaginationWindow(
            items=result.scalars().unique().all(),
            count=await User.get_user_count(info),
        )

    @staticmethod
    async def get_user(
        info: Info,
        id: Optional[int] = None,
        email: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional["User"]:
        async_db = info.context["request"].state.async_db

        stmt = select(DBUser)
        if id:
            stmt = stmt.where(DBUser.id == id)
        if email:
            stmt = stmt.where(DBUser.email.ilike(f"%{email}%"))
        if notes:
            stmt = stmt.where(DBUser.notes.ilike(f"%{notes}%"))
        stmt = User.get_stmt_with_options(info, stmt)

        result = await async_db.execute(stmt)
        return result.scalars().unique().first()

    @staticmethod
    async def get_user_count(info: Info) -> int:
        async_db = info.context["request"].state.async_db
        user = info.context["request"].state.user

        if user.id not in count_cache:
            stmt = select(func.count(DBUser.id))

            result = await async_db.execute(stmt)
            count_cache[user.id] = result.scalar()

        return count_cache[user.id]

    @staticmethod
    async def create_user(
        info: Info,
        email: str,
        password: str,
        is_active: Optional[bool] = True,
        is_ops: Optional[bool] = False,
        is_superuser: Optional[bool] = False,
        notes: Optional[str] = None,
    ) -> "User":
        async_db = info.context["request"].state.async_db

        _id = (
            await async_db.execute(
                insert(DBUser)
                .values(
                    email=email,
                    hashed_password=get_password_hash(password),
                    is_active=is_active,
                    is_ops=is_ops,
                    is_superuser=is_superuser,
                    notes=notes,
                )
                .returning(DBUser.id)
            )
        ).scalar()

        result = await async_db.execute(
            User.get_stmt_with_options(
                info, select(DBUser).where(DBUser.id == _id)
            )
        )
        return result.scalars().unique().first()

    @staticmethod
    async def update_user(
        info: Info,
        id: int,
        email: Optional[str] = None,
        password: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_ops: Optional[bool] = None,
        is_superuser: Optional[bool] = None,
        notes: Optional[str] = None,
    ) -> bool:
        async_db = info.context["request"].state.async_db

        stmt = update(DBUser).where(DBUser.id == id)
        if email:
            stmt = stmt.values(email=email)
        if password:
            stmt = stmt.values(hashed_password=get_password_hash(password))
        if is_active is not None:
            stmt = stmt.values(is_active=is_active)
        if is_ops is not None:
            stmt = stmt.values(is_ops=is_ops)
        if is_superuser is not None:
            stmt = stmt.values(is_superuser=is_superuser)
        if notes:
            stmt = stmt.values(notes=notes)

        await async_db.execute(stmt)

        result = await async_db.execute(stmt)
        await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def delete_user(info: Info, id: int) -> bool:
        async_db = info.context["request"].state.async_db

        result = await async_db.execute(
            delete(DBUser).where(DBUser.id == id)
        )
        await async_db.commit()
        return result.rowcount > 0
