import asyncio
import async_timeout
from typing import AsyncGenerator, List, Optional, Dict

import strawberry
import redis.asyncio as redis
from strawberry.types import Info
from strawberry.scalars import JSON

from .auth import IsAuthenticated, IsAdmin, IsSuperUser, EnsureUser
from .file import File
from .port import Port, PortUser
from .port_forward import PortForwardRule
from .server import Server, ServerUser, ServerUsage
from .user import User
from .task import task
from .channel import subscribe
from .utils import PaginationWindow


@strawberry.type
class Query:
    user: Optional[User] = strawberry.field(
        resolver=User.get_user, permission_classes=[IsAuthenticated]
    )
    users: List[User] = strawberry.field(
        resolver=User.get_users, permission_classes=[IsAuthenticated]
    )
    paginated_users: PaginationWindow[User] = strawberry.field(
        resolver=User.get_paginated_users, permission_classes=[IsAuthenticated]
    )
    files: List[File] = strawberry.field(
        resolver=File.get_files, permission_classes=[IsAuthenticated]
    )
    paginated_files: PaginationWindow[File] = strawberry.field(
        resolver=File.get_paginated_files, permission_classes=[IsAuthenticated]
    )
    port: Optional[Port] = strawberry.field(
        resolver=Port.get_port, permission_classes=[IsAuthenticated]
    )
    ports: List[Port] = strawberry.field(
        resolver=Port.get_ports, permission_classes=[IsAuthenticated]
    )
    paginated_ports: PaginationWindow[Port] = strawberry.field(
        resolver=Port.get_paginated_ports, permission_classes=[IsAuthenticated]
    )
    rule_options: List[str] = strawberry.field(
        resolver=Port.get_rule_options, permission_classes=[IsAuthenticated]
    )
    server: Optional[Server] = strawberry.field(
        resolver=Server.get_server, permission_classes=[IsAuthenticated]
    )
    servers: List[Server] = strawberry.field(
        resolver=Server.get_servers, permission_classes=[IsAuthenticated]
    )
    connect_server: JSON = strawberry.field(
        resolver=Server.connect_server, permission_classes=[IsAuthenticated]
    )
    paginated_servers: PaginationWindow[Server] = strawberry.field(
        resolver=Server.get_paginated_servers,
        permission_classes=[IsAuthenticated],
    )
    port_forward_rule: Optional[PortForwardRule] = strawberry.field(
        resolver=PortForwardRule.get_port_forward_rule,
        permission_classes=[IsAuthenticated],
    )


@strawberry.type
class Mutation:
    create_user: User = strawberry.field(resolver=User.create_user)
    update_user: bool = strawberry.field(
        resolver=User.update_user, permission_classes=[IsSuperUser]
    )
    delete_user: bool = strawberry.field(
        resolver=User.delete_user, permission_classes=[IsSuperUser]
    )
    upload_file: File = strawberry.field(
        resolver=File.upload_file, permission_classes=[IsSuperUser]
    )
    update_file: bool = strawberry.field(
        resolver=File.update_file, permission_classes=[IsSuperUser]
    )
    delete_file: bool = strawberry.field(
        resolver=File.delete_file, permission_classes=[IsSuperUser]
    )
    add_server: bool = strawberry.field(
        resolver=Server.add_server, permission_classes=[IsSuperUser]
    )
    update_server: bool = strawberry.field(
        resolver=Server.update_server, permission_classes=[IsSuperUser]
    )
    delete_server: bool = strawberry.field(
        resolver=Server.delete_server, permission_classes=[IsSuperUser]
    )
    add_server_user: bool = strawberry.field(
        resolver=ServerUser.add_server_user, permission_classes=[IsSuperUser]
    )
    update_server_user: bool = strawberry.field(
        resolver=ServerUser.update_server_user, permission_classes=[IsSuperUser]
    )
    delete_server_user: bool = strawberry.field(
        resolver=ServerUser.delete_server_user, permission_classes=[IsSuperUser]
    )
    add_port: bool = strawberry.field(
        resolver=Port.add_port, permission_classes=[IsAdmin]
    )
    update_port: bool = strawberry.field(
        resolver=Port.update_port, permission_classes=[IsAdmin]
    )
    delete_port: bool = strawberry.field(
        resolver=Port.delete_port, permission_classes=[IsAdmin]
    )
    add_port_user: bool = strawberry.field(
        resolver=PortUser.add_port_user, permission_classes=[IsAdmin]
    )
    update_port_user: bool = strawberry.field(
        resolver=PortUser.update_port_user, permission_classes=[IsAdmin]
    )
    delete_port_user: bool = strawberry.field(
        resolver=PortUser.delete_port_user, permission_classes=[IsAdmin]
    )


async def count(info: Info, target: int = 1) -> AsyncGenerator[int, None]:
    from tasks.test import test_task

    test_task()
    for i in range(target):
        yield i
        await asyncio.sleep(0.5)


@strawberry.type
class Subscription:
    subscribe_channel: AsyncGenerator[JSON, None] = strawberry.subscription(
        resolver=subscribe, permission_classes=[]
    )
    task: AsyncGenerator[JSON, None] = strawberry.subscription(
        resolver=task, permission_classes=[]
    )
    count: AsyncGenerator[int, None] = strawberry.subscription(
        resolver=count, permission_classes=[]
    )
    server_usage: AsyncGenerator[ServerUsage, None] = strawberry.subscription(
        resolver=Server.get_usage, permission_classes=[IsAuthenticated]
    )


schema = strawberry.Schema(
    query=Query, mutation=Mutation, subscription=Subscription
)
