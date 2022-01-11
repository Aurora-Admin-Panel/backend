import uvicorn
import typing as t
from sqlalchemy.exc import IntegrityError
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

import sentry_sdk
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.api.v1.auth import auth_router
from app.api.v1.users import users_router
from app.api.v1.servers import servers_router
from app.api.v1.ports import ports_router
from app.api.v1.forward_rule import forward_rule_router
from app.api.v2.servers import servers_v2_router
from app.api.v2.ports import ports_v2_router
from app.api.v2.users import users_v2_router
from app.db.crud.server import get_server, get_server_with_ports_usage
from app.core import config
from app.db.session import db_session
from app.core.auth import get_current_active_user
from app.utils.ip import get_external_ip


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

sentry_sdk.init(
    release=f"{config.BACKEND_VERSION}",
    environment=f"{config.ENVIRONMENT}",
    dsn="https://c1a19cfeb74045f8912e5cb449c1071d@sentry.leishi.io/2",
    integrations=[SqlalchemyIntegration()],
)
sentry_sdk.set_tag('panel.ip', get_external_ip())


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
async def db_session_middleware(request: Request, call_next):
    with db_session() as db:
        request.state.db = db
        try:
            response = await call_next(request)
            return response
        except IntegrityError as e:
            return JSONResponse(
                status_code=400,
                content={"detail": str(e.orig)})


@app.get("/api/v1")
async def root():
    with db_session() as db:
        server = get_server_with_ports_usage(db, 34)
    print([p for p in server.ports])
    return {"message": "Hello World"}


# Routers
app.include_router(
    users_router,
    prefix="/api/v1",
    tags=["v1.users"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    users_v2_router,
    prefix="/api/v2",
    tags=["v2.users"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    servers_router,
    prefix="/api/v1",
    tags=["v1.servers"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    servers_v2_router,
    prefix="/api/v2",
    tags=["v2.servers"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    ports_router,
    prefix="/api/v1",
    tags=["v1.ports"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    ports_v2_router,
    prefix="/api/v2",
    tags=["v2.ports"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    forward_rule_router,
    prefix="/api/v1",
    tags=["v1.port_rule"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(auth_router, prefix="/api", tags=["auth"])

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        reload=(not config.ENVIRONMENT == "PROD"),
        port=8888,
    )
