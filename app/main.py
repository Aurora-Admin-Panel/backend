from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware
from strawberry.fastapi import GraphQLRouter
from strawberry.subscriptions import (
    GRAPHQL_TRANSPORT_WS_PROTOCOL,
    GRAPHQL_WS_PROTOCOL,
)
from loguru import logger

from app.api.auth import auth_router
from app.core import config
from app.graphql.schema import schema
from app.websocket.handler import handler
from tasks.server import servers_usage_runner


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting lifespan")
    logger.info("Starting servers usage runner")
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
