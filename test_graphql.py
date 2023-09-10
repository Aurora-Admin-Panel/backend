import typing
from typing import Any, List, Optional, Union

import strawberry
from app.core import config
from app.db.graphql.user import User
from app.db.models import Port as DBPort
from app.db.models import PortUser as DBPortUser
from app.db.models import Server as DBServer
from app.db.models import ServerUser as DBServerUser
from app.db.models import User as DBUser
from app.db.session import db_session
from sqlalchemy import select
from sqlalchemy.orm import joinedload, lazyload, selectinload
from starlette.requests import Request
from starlette.responses import Response
from starlette.websockets import WebSocket
from strawberry.asgi import GraphQL
from strawberry.dataloader import DataLoader
from strawberry.types import Info


def get_author_for_book(root) -> "Author":
    return Author(name="Michael Crichton")


@strawberry.type
class Book:
    title: str
    author: "Author" = strawberry.field(resolver=get_author_for_book)


def get_books_for_author(root):
    return [Book(title="Jurassic Park")]


@strawberry.type
class Author:
    name: str
    books: typing.List[Book] = strawberry.field(resolver=get_books_for_author)


def get_authors(root) -> typing.List[Author]:
    return [Author(name="Michael Crichton")]


def load_users(info: Info) -> typing.List[User]:
    print('load_users')
    return select(DBUser)


@strawberry.type
class Query:

    @strawberry.field
    async def users(self, info: Info) -> typing.List[User]:
        # print(info.schema)
        with db_session() as db:
            query = db.query(DBUser).options(joinedload(DBUser.servers))
            print(query.statement.compile(compile_kwargs={"literal_binds": True}))
            # result = await conn.query(DBUser).options(joinedload(DBUser.servers))
            return query.all()


schema = strawberry.Schema(query=Query)
# app = MyGraphQL(schema)
