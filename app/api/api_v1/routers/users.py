import typing as t
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from fastapi import APIRouter, Request, Depends, Response, encoders
from fastapi.encoders import jsonable_encoder

from app.core.security import verify_password
from app.db.session import get_db
from app.db.crud.user import (
    get_users,
    get_user,
    create_user,
    delete_user,
    edit_user,
    edit_me,
    get_user_servers,
    get_user_ports,
)
from app.db.schemas.user import (
    UserCreate,
    UserEdit,
    User,
    UserOut,
    UserOpsOut,
    MeEdit,
    UserServerOut,
)
from app.core.auth import get_current_active_user, get_current_active_superuser
from app.utils.size import get_readable_size

users_router = r = APIRouter()


@r.get(
    "/users",
    response_model=t.List[UserOpsOut],
    response_model_exclude_none=True,
)
async def users_list(
    response: Response,
    db=Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Get all users
    """
    users = jsonable_encoder(get_users(db))
    # This is necessary for react-admin to work
    response.headers["Content-Range"] = f"0-9/{len(users)}"
    users_with_usage = []
    for user in users:
        for port in user.get("allowed_ports", []):
            if port["port"]["usage"]:
                user["download_usage"] = port["port"]["usage"].get(
                    "download", 0
                )
                user["readable_download_usage"] = get_readable_size(
                    user["download_usage"]
                )
                user["upload_usage"] = port["port"]["usage"].get("upload", 0)
                user["readable_upload_usage"] = get_readable_size(
                    user["upload_usage"]
                )
        users_with_usage.append(user)
    return users_with_usage


@r.get("/users/me", response_model=User, response_model_exclude_none=True)
async def user_me(current_user=Depends(get_current_active_user)):
    """
    Get own user
    """
    return current_user


@r.put("/users/me", response_model=User, response_model_exclude_none=True)
async def user_me_edit(
    request: Request,
    user: MeEdit,
    db=Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Update me
    """
    if user.new_password and not user.prev_password:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="No old password provided"
        )
    elif user.prev_password:
        if not verify_password(
            user.prev_password, current_user.hashed_password
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Password not match"
            )
        user.prev_password = None
    return edit_me(db, current_user, user)


@r.get(
    "/users/{user_id}",
    response_model=UserOpsOut,
)
async def user_details(
    request: Request,
    user_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_active_superuser),
):
    """
    Get any user details
    """
    user = get_user(db, user_id)
    return jsonable_encoder(user)
    # return encoders.jsonable_encoder(
    #     user, skip_defaults=True, exclude_none=True,
    # )


@r.post("/users", response_model=UserOpsOut, response_model_exclude_none=True)
async def user_create(
    request: Request,
    user: UserCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_active_superuser),
):
    """
    Create a new user
    """
    return jsonable_encoder(create_user(db, user))


@r.put(
    "/users/{user_id}", response_model=UserOpsOut, response_model_exclude_none=True
)
async def user_edit(
    request: Request,
    user_id: int,
    user: UserEdit,
    db=Depends(get_db),
    current_user=Depends(get_current_active_superuser),
):
    """
    Update existing user
    """
    return jsonable_encoder(edit_user(db, user_id, user))


@r.delete(
    "/users/{user_id}", response_model=User, response_model_exclude_none=True
)
async def user_delete(
    request: Request,
    user_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_active_superuser),
):
    """
    Delete existing user
    """
    return delete_user(db, user_id)


@r.get(
    "/users/{user_id}/servers",
    response_model=t.List[UserServerOut],
    response_model_exclude_none=True,
)
async def user_servers_get(
    request: Request,
    user_id: int,
    db=Depends(get_db),
    user=Depends(get_current_active_superuser),
):
    """
    Get user's servers
    """
    user_servers = jsonable_encoder(get_user_servers(db, user_id))
    user_ports = get_user_ports(db, user_id)
    formatted_user_servers = []
    for server in jsonable_encoder(user_servers):
        server_ports = []
        for port_user in user_ports:
            if server["server_id"] == port_user.port.server.id:
                server_ports.append(port_user)
        server["ports"] = jsonable_encoder(server_ports)
        formatted_user_servers.append(server)
    return formatted_user_servers
