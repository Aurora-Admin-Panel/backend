import asyncio
from typing import Optional, Annotated
from contextlib import asynccontextmanager

import jwt
import uvicorn
from app.api.auth import auth_router
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting lifespan")
    from tasks import servers_usage_runner
    servers_usage_runner.schedule(delay=0)
    yield

app = FastAPI(
    title=config.PROJECT_NAME,
    lifespan=lifespan,
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


@app.get("/api/v1")
async def root(server_id: int):
    pass


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await handler.init(websocket)
    await handler.run_forever(websocket)


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
