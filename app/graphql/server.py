import typing
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional, AsyncGenerator
from strawberry.types.nodes import Selection
from typing_extensions import Annotated

import strawberry
from sqlalchemy import func, and_, select, insert, update, delete
from sqlalchemy.orm import Query, joinedload
from strawberry.scalars import JSON
from strawberry.types import Info

import tasks
from app.core import config
from app.db.models import Port as DBPort
from app.db.models import PortUser as DBPortUser
from app.db.models import Server as DBServer, ServerUsage as DBServerUsage
from app.db.models import ServerUser as DBServerUser
from app.db.models import User as DBUser
from app.utils.permission import has_permission_of_server
from app.db.async_session import async_db_session
from app.utils.selection import get_selections

from .utils import PaginationWindow

if TYPE_CHECKING:
    from .file import File
    from .port import Port
    from .user import User


count_cache: typing.Dict[int, int] = {}


async def get_server_port_total(root: "Server") -> int:
    return len(root.ports)


async def get_server_port_used(root: "Server") -> int:
    return sum([1 for port in root.ports if port.forward_rule is not None])


@strawberry.type
class ServerUsage:
    id: int
    server_id: int
    timestamp: datetime
    cpu: int = strawberry.field(resolver=lambda root: round(root.cpu))
    memory: int = strawberry.field(resolver=lambda root: round(root.memory))
    disk: int = strawberry.field(resolver=lambda root: round(root.disk))


@strawberry.type
class ServerUser:
    id: int
    server_id: int
    user_id: int
    download: int
    upload: int
    notes: Optional[str]
    config: JSON
    user: Annotated["User", strawberry.lazy(".user")]
    server: Annotated["Server", strawberry.lazy(".server")]

    @staticmethod
    async def add_server_user(
        info: Info,
        server_id: int,
        user_id: int,
        notes: Optional[str] = None,
    ) -> bool:
        stmt = insert(DBServerUser).values(
            server_id=server_id,
            user_id=user_id,
            notes=notes,
        )

        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def update_server_user(
        info: Info,
        server_id: int,
        user_id: int,
        notes: Optional[str] = None,
    ) -> bool:
        stmt = update(DBServerUser).where(server_id == server_id, user_id == user_id)

        if notes:
            stmt = stmt.values(notes=notes)

        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def delete_server_user(
        info: Info,
        server_id: int,
        user_id: int,
    ) -> bool:
        stmt = delete(DBServerUser).where(server_id == server_id, user_id == user_id)

        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            await async_db.commit()
        return result.rowcount > 0


@strawberry.type
class Server:
    id: int
    name: str
    address: str
    host: Optional[str]
    port: Optional[int]
    user: Optional[str]
    key_file_id: Optional[int]
    config: JSON
    ssh_password: Optional[str]
    ssh_password_set: bool = strawberry.field(
        resolver=lambda root: root.ssh_password is not None
    )
    sudo_password: Optional[str]
    sudo_password_set: bool = strawberry.field(
        resolver=lambda root: root.sudo_password is not None
    )
    is_active: bool

    port_used: int = strawberry.field(
        resolver=lambda root: sum(
            [1 for port in root.ports if port.forward_rule is not None]
        )
    )
    port_total: int = strawberry.field(resolver=lambda root: len(root.ports))
    download_total: Decimal = strawberry.field(
        resolver=lambda root: sum(user.download for user in root.allowed_users)
    )
    upload_total: Decimal = strawberry.field(
        resolver=lambda root: sum(user.upload for user in root.allowed_users)
    )

    ports: typing.List[Annotated["Port", strawberry.lazy(".port")]]
    users: typing.List[Annotated["User", strawberry.lazy(".user")]]
    allowed_users: typing.List[Annotated["ServerUser", strawberry.lazy(".server")]]
    key_file: Annotated["File", strawberry.lazy(".file")]

    @staticmethod
    def set_options(stmt: Query, selections: List[Selection]) -> Query:
        if (
            (selection := get_selections(selections, "ports"))
            or get_selections(selections, "portUsed")
            or get_selections(selections, "portTotal")
        ):
            options = joinedload(DBServer.ports)
            sub_options = []
            if (
                selection and get_selections(selection.selections, "forwardRule")
            ) or get_selections(selections, "portUsed"):
                sub_options.append(joinedload(DBPort.forward_rule))
            if selection and get_selections(selection.selections, "usage"):
                sub_options.append(joinedload(DBPort.usage))
            if len(sub_options) > 0:
                options = options.options(*sub_options)
            stmt = stmt.options(options)
        if selection := get_selections(selections, "users"):
            options = joinedload(DBServer.users)
            stmt = stmt.options(options)
        if (
            (selection := get_selections(selections, "allowedUsers"))
            or get_selections(selections, "downloadTotal")
            or get_selections(selections, "uploadTotal")
        ):
            options = joinedload(DBServer.allowed_users)
            if selection and (
                selection := get_selections(selection.selections, "user")
            ):
                options = options.joinedload(DBServerUser.user)
            stmt = stmt.options(options)
        return stmt

    @staticmethod
    async def get_servers(info: Info, order_by: str = "name") -> List["Server"]:
        stmt = Server.set_options(
            select(DBServer)
            .order_by(order_by)
            .options(joinedload(DBServer.allowed_users)),
            get_selections(info.selected_fields, info.field_name).selections,
        )

        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            return result.scalars().unique().all()

    @staticmethod
    async def get_paginated_servers(
        info: Info, order_by: str = "name", limit: int = 10, offset: int = 0
    ) -> PaginationWindow["Server"]:
        stmt = Server.set_options(
            select(DBServer)
            .order_by(order_by)
            .options(joinedload(DBServer.allowed_users))
            .where(DBServer.is_active == True),
            get_selections(info.selected_fields, f"{info.field_name}.items").selections,
        )
        stmt = stmt.limit(limit).offset(offset)

        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            return PaginationWindow(
                items=result.scalars().unique().all(),
                count=(await Server.get_server_count(info)),
            )

    @staticmethod
    async def get_server(
        info: Info,
        id: Optional[int] = None,
        name: Optional[str] = None,
        address: Optional[str] = None,
    ) -> Optional["Server"]:
        stmt = Server.set_options(
            select(DBServer),
            get_selections(info.selected_fields, info.field_name).selections,
        )
        if id:
            stmt = stmt.where(DBServer.id == id)
        if name:
            stmt = stmt.where(DBServer.name.ilike(f"%{name}%"))
        if address:
            stmt = stmt.where(DBServer.address.ilike(f"%{address}%"))

        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            return result.scalars().unique().first()

    @staticmethod
    async def get_server_count(info: Info) -> int:
        user = info.context["request"].state.user

        if user.id not in count_cache:
            stmt = select(func.count(DBServer.id, distinct=True))
            if not user.is_superuser:
                stmt = stmt.join(
                    DBServer.allowed_users.and_(DBServerUser.user_id == user.id)
                )
            stmt = stmt.where(DBServer.is_active == True)

            async with async_db_session() as async_db:
                result = await async_db.execute(stmt)
                count_cache[user.id] = result.scalar()
        return count_cache[user.id]

    @staticmethod
    async def add_server(
        info: Info,
        name: str,
        address: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        key_file_id: Optional[int] = None,
        config: Optional[JSON] = None,
        ssh_password: Optional[str] = None,
        sudo_password: Optional[str] = None,
    ) -> bool:
        stmt = insert(DBServer).values(
            name=name,
            address=address,
            host=host if host else address,
            port=port if port else 22,
            user=user if user else "root",
            key_file_id=key_file_id,
            config=config if config else {},
            ssh_password=ssh_password,
            sudo_password=sudo_password,
        )

        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def update_server(
        info: Info,
        id: int,
        name: Optional[str] = None,
        address: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        key_file_id: Optional[int] = None,
        config: Optional[JSON] = None,
        ssh_password: Optional[str] = None,
        sudo_password: Optional[str] = None,
    ) -> bool:
        stmt = update(DBServer).where(DBServer.id == id)
        if name:
            stmt = stmt.values(name=name)
        if address:
            stmt = stmt.values(address=address)
        if host:
            stmt = stmt.values(host=host)
        if port:
            stmt = stmt.values(port=port)
        if user:
            stmt = stmt.values(user=user)
        if key_file_id:
            stmt = stmt.values(key_file_id=key_file_id)
        if config:
            stmt = stmt.values(config=config)
        if ssh_password:
            stmt = stmt.values(ssh_password=ssh_password)
        if sudo_password:
            stmt = stmt.values(sudo_password=sudo_password)

        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def delete_server(info: Info, id: int) -> bool:
        stmt = delete(DBServer).where(DBServer.id == id)

        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def connect_server(info: Info, server_id: int) -> JSON:
        user = info.context["request"].state.user
        if not has_permission_of_server(user, server_id):
            return {"error": "Permission denied"}

        result = tasks.connect_runner2(server_id)
        while True:
            res = result.get()
            if res is not None:
                break
            await asyncio.sleep(0.1)
        return res

    @staticmethod
    async def get_usage(
        info: Info, server_id: int
    ) -> AsyncGenerator[ServerUsage, None]:
        user = info.context["request"].state.user
        if not await has_permission_of_server(user, server_id):
            yield {"error": "Permission denied"}
            return

        failed_count = 0
        while True:
            async with async_db_session() as async_db:
                stmt = (
                    select(DBServerUsage)
                    .where(DBServerUsage.server_id == server_id)
                    .order_by(DBServerUsage.timestamp.desc())
                    .limit(1)
                )
                result = await async_db.execute(stmt)
                data = result.scalars().unique().first()
                if data and data.timestamp > datetime.now() - timedelta(
                    seconds=config.SERVER_USAGE_INTERVAL_SECONDS * 10
                ):
                    yield data
                elif failed_count > 10:
                    break
                else:
                    failed_count += 1
            await asyncio.sleep(config.SERVER_USAGE_INTERVAL_SECONDS)
