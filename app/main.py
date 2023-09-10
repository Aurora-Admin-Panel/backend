import asyncio
from typing import Optional, Annotated

import jwt
import sentry_sdk
import uvicorn
from app.api.v1.auth import auth_router
from app.api.v1.forward_rule import forward_rule_router
from app.api.v1.ports import ports_router
from app.api.v1.servers import servers_router
from app.api.v1.users import users_router
from app.api.v2.ports import ports_v2_router
from app.api.v2.servers import servers_v2_router
from app.api.v2.users import users_v2_router
from app.api.v3.users import users_v3_router
from app.core import config, security
from app.core.auth import get_current_active_user
from app.db.async_session import async_db_session
from app.graphql.schema import schema
from app.graphql.user import User
from app.db.session import db_session
from app.utils.ip import get_external_ip
from app.db.crud.user import get_user_by_email
from app.websocket.handler import handler
from fastapi import Depends, FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security.utils import get_authorization_scheme_param
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sqlalchemy.exc import IntegrityError
from strawberry.types import Info
from sse_starlette.sse import EventSourceResponse
from strawberry.fastapi import GraphQLRouter
from strawberry.subscriptions import (
    GRAPHQL_TRANSPORT_WS_PROTOCOL,
    GRAPHQL_WS_PROTOCOL,
)

app = FastAPI(
    title=config.PROJECT_NAME,
    docs_url="/api/docs",
    openapi_url="/api",
    version=config.BACKEND_VERSION,
)
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if config.ENABLE_SENTRY:
    sentry_sdk.init(
        release=f"{config.BACKEND_VERSION}",
        environment=f"{config.ENVIRONMENT}",
        dsn="https://5622016b92cf4a039cbab7cba10d64f2@sentry.leishi.io/2",
        integrations=[SqlalchemyIntegration(), RedisIntegration()],
        traces_sample_rate=1.0,
    )
    sentry_sdk.set_tag("panel.ip", get_external_ip())


@app.middleware("http")
async def sentry_exception(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        if config.ENABLE_SENTRY:
            with sentry_sdk.push_scope() as scope:
                scope.set_context("request", request)
                scope.user = {"ip_address": request.client.host}
                sentry_sdk.capture_exception(e)
        raise e


@app.middleware("http")
async def user_middleware(request: Request, call_next):
    request.state.user = None
    with db_session() as db:
        try:
            authorization = request.headers.get("Authorization")
            scheme, token = get_authorization_scheme_param(authorization)
            if authorization and scheme.lower() == "bearer":
                payload = jwt.decode(
                    token, config.SECRET_KEY, algorithms=[security.ALGORITHM]
                )
                email: str = payload.get("sub")
                if email is not None:
                    request.state.user = get_user_by_email(db, email)
        except jwt.PyJWTError:
            pass
    return await call_next(request)


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/graphql"):
        async with async_db_session() as async_db:
            request.state.async_db = async_db
            return await call_next(request)
    with db_session() as db:
        request.state.db = db
        try:
            response = await call_next(request)
            return response
        except IntegrityError as e:
            return JSONResponse(
                status_code=400, content={"detail": str(e.orig)}
            )


@app.get("/api/v1")
async def root(server_id: int):
    from tasks.utils.connection import connect
    from tasks.utils.exception import AuroraException
    from tasks.server import connect_runner2
    from app.db.crud.server import get_server
    from app.db.session import db_session

    with db_session() as db:
        server = get_server(db, server_id)
    # return connect_runner2(server_id).get(blocking=True)

    try:
        with connect(server_id=server_id) as c:
            c.run("cat /etc/os-release")
            return {"success": True, "server_id": server_id}
    except AuroraException as e:
        return {"error": str(e), "server_id": server_id}

@app.get("/api/stream")
async def message_stream(request: Request):
    def new_messages():
        # Add logic here to check for new messages
        yield "Hello World"

    async def event_generator():
        while True:
            # If client closes connection, stop sending events
            if await request.is_disconnected():
                break

            # Checks for new messages and return them to client if any
            if new_messages():
                yield {
                    "event": "new_message",
                    "id": "message_id",
                    "retry": 15000,
                    "data": "message_content",
                }

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    token = await websocket.receive_text()
    payload = jwt.decode(
        token, config.SECRET_KEY, algorithms=[security.ALGORITHM]
    )
    email: str = payload.get("sub")
    if email is None:
        websocket.close()

    async with async_db_session() as async_db:
        user = await User.get_user_by_email(async_db, email)
    if not user:
        await websocket.send_json(
            {
                "type": "error",
                "message": "Not authenticated, closing connection",
            }
        )
        websocket.close()
    await websocket.send_json(
        {"type": "response", "message": f"Hello, {user.email}!"}
    )
    await handler.run_forever(websocket)


# Routers
app.include_router(
    users_router,
    prefix="/api/v1",
    tags=["v1", "users"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    users_v2_router,
    prefix="/api/v2",
    tags=["v2", "users"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    servers_router,
    prefix="/api/v1",
    tags=["v1", "servers"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    servers_v2_router,
    prefix="/api/v2",
    tags=["v2", "servers"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    ports_router,
    prefix="/api/v1",
    tags=["v1", "ports"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    ports_v2_router,
    prefix="/api/v2",
    tags=["v2", "ports"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    forward_rule_router,
    prefix="/api/v1",
    tags=["v1", "port_rule"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    users_v3_router,
    prefix="/api/v3",
    tags=["v3", "users"],
    dependencies=[Depends(get_current_active_user)],
)
graphql_app = GraphQLRouter(
    schema,
    subscription_protocols=[
        GRAPHQL_TRANSPORT_WS_PROTOCOL,
        GRAPHQL_WS_PROTOCOL,
    ],
)
app.include_router(graphql_app, prefix="/api/graphql")
app.include_router(auth_router, prefix="/api", tags=["auth"])


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        reload=(not config.ENVIRONMENT == "PROD"),
        port=8888,
    )
