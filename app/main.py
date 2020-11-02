import uvicorn
from fastapi import FastAPI, Depends
from starlette.requests import Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.utils.gost import get_gost_config
from app.api.api_v1.routers.auth import auth_router
from app.api.api_v1.routers.users import users_router
from app.api.api_v1.routers.servers import servers_router
from app.api.api_v1.routers.ports import ports_router
from app.api.api_v1.routers.forward_rule import forward_rule_router
from app.core import config
from app.db.session import SessionLocal
from app.core.auth import get_current_active_user
from app.tasks import celery_app


app = FastAPI(
    title=config.PROJECT_NAME, docs_url="/api/docs", openapi_url="/api"
)
origins = ["*", "http://localhost:3000/", "http://192.168.1.119:8000", "https://monitor.2cn.io"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    request.state.db = SessionLocal()
    response = await call_next(request)
    request.state.db.close()
    return response


@app.get("/api/v1")
async def root():
    return {"message": "Hello World"}


@app.get("/api/v1/task")
async def run_task():
    celery_app.send_task("app.tasks.gost.gost_runner", kwargs={
        'rule_id': 2,
        'host': 'sj2',
        'update_gost': True
    })
    return {"message": "ok"}


# Routers
app.include_router(
    users_router,
    prefix="/api/v1",
    tags=["users"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    servers_router,
    prefix="/api/v1",
    tags=["servers"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    ports_router,
    prefix="/api/v1",
    tags=["ports"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(
    forward_rule_router,
    prefix="/api/v1",
    tags=["forward rule"],
    dependencies=[Depends(get_current_active_user)],
)
app.include_router(auth_router, prefix="/api", tags=["auth"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", reload=True, port=8888)
