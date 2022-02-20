import typing as t
from collections import defaultdict
from fastapi import HTTPException, status
from fastapi import APIRouter, Request, Depends, Response
from fastapi.encoders import jsonable_encoder

from app.core.security import verify_password
from app.db.session import get_db
from app.db.crud.user import (
    get_users_with_ports_usage,
    get_user,
    get_user_by_email,
    create_user,
    delete_user,
    edit_user,
    edit_me,
    get_user_servers,
    get_user_ports_with_usage,
)
from app.db.crud.server import delete_server_user
from app.db.crud.port import delete_port_user
from app.db.crud.port_usage import edit_port_usage
from app.db.crud.port_forward import (
    get_forward_rule_for_user,
    delete_forward_rule_by_id,
)
from app.db.schemas.user import (
    UserCreate,
    UserEdit,
    UserDelete,
    User,
    UserOut,
    UserOpsOut,
    MeEdit,
    UserServerOut,
)
from app.db.schemas.port_usage import PortUsageEdit
from app.core.auth import get_current_active_user, get_current_active_superuser
from app.utils.size import get_readable_size
from app.utils.tasks import trigger_port_clean

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
    Get all users with usage
    """
    users = jsonable_encoder(get_users_with_ports_usage(db))
    # This is necessary for react-admin to work
    response.headers["Content-Range"] = f"0-9/{len(users)}"
    users_with_usage = []
    for user in users:
        user["download_usage"] = 0
        user["upload_usage"] = 0
        for port in user.get("allowed_ports", []):
            if port["port"]["usage"]:
                user["download_usage"] += port["port"]["usage"].get(
                    "download", 0
                )
                user["upload_usage"] += port["port"]["usage"].get("upload", 0)
        user["readable_download_usage"] = get_readable_size(
            user["download_usage"]
        )
        user["readable_upload_usage"] = get_readable_size(user["upload_usage"])
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
    db_user = get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Account already exists",
        )
    return create_user(db, user)


@r.put(
    "/users/{user_id}",
    response_model=UserOpsOut,
    response_model_exclude_none=True,
)
async def user_edit(
    request: Request,
    user_id: int,
    user_edit: UserEdit,
    db=Depends(get_db),
    current_user=Depends(get_current_active_superuser),
):
    """
    Update existing user
    """
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_edit.clear_rules:
        for port in user.ports:
            edit_port_usage(
                db,
                port.id,
                PortUsageEdit(
                    port_id=port.id,
                    download=0,
                    upload=0,
                    download_accumulate=0,
                    upload_accumulate=0,
                    download_checkpoint=0,
                    upload_checkpoint=0,
                ),
            )
            if port.forward_rule:
                trigger_port_clean(port.server, port, False)
                delete_forward_rule_by_id(db, port.forward_rule.id)
        for port_user in user.allowed_ports:
            delete_port_user(
                db, port_user.port.server.id, port_user.port_id, user.id
            )
        for server_user in user.allowed_servers:
            delete_server_user(db, server_user.server_id, user.id)
    return edit_user(db, user_id, user_edit)


@r.delete(
    "/users/{user_id}",
    response_model=UserOut,
    response_model_exclude_none=True,
)
async def user_delete(
    request: Request,
    user_id: int,
    user_delete: UserDelete,
    db=Depends(get_db),
    current_user=Depends(get_current_active_superuser),
):
    """
    Delete existing user
    """
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_delete.remove_rule:
        for port in user.ports:
            edit_port_usage(
                db,
                port.id,
                PortUsageEdit(
                    port_id=port.id,
                    download=0,
                    upload=0,
                    download_accumulate=0,
                    upload_accumulate=0,
                    download_checkpoint=0,
                    upload_checkpoint=0,
                ),
            )
            if port.forward_rule:
                trigger_port_clean(port.server, port, False)
                delete_forward_rule_by_id(db, port.forward_rule.id)
        for port_user in user.allowed_ports:
            delete_port_user(
                db, port_user.port.server.id, port_user.port_id, user.id
            )
        for server_user in user.allowed_servers:
            delete_server_user(db, server_user.server_id, user.id)
    return delete_user(db, user)


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
    user_ports = jsonable_encoder(get_user_ports_with_usage(db, user_id))
    port_by_server = defaultdict(list)
    for port_user in user_ports:
        port_user["usage"] = port_user["port"]["usage"]
        port_by_server[port_user["port"]["server_id"]].append(port_user)
    formatted_user_servers = []
    for server in user_servers:
        server["ports"] = port_by_server[server["server_id"]]
        formatted_user_servers.append(server)
    return formatted_user_servers
