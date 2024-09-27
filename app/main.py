import asyncio
from typing import Optional, Annotated

import jwt
import sentry_sdk
import uvicorn
from app.api.auth import auth_router
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
from starlette.middleware import Middleware
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
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ],
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


@app.get("/api/v1")
async def root(server_id: int):
    pass


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await handler.init(websocket)
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
        GRAPHQL_WS_PROTOCOL,
        GRAPHQL_TRANSPORT_WS_PROTOCOL,
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
