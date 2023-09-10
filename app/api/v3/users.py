from fastapi import APIRouter

users_v3_router = r = APIRouter()


@r.get("/users")
async def users_list():
    return {"message": "OK"}
