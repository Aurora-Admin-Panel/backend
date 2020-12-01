import typing as t
from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Depends,
    Response,
    encoders,
)
from fastapi.encoders import jsonable_encoder

from app.db.session import get_db
from app.db.schemas.server import (
    ServerOut,
    ServerOpsOut,
    ServerCreate,
    ServerEdit,
    ServerUserEdit,
    ServerUserOut,
    ServerUserOpsOut,
    ServerUserCreate,
)
from app.db.crud.server import (
    get_servers,
    get_server,
    create_server,
    edit_server,
    delete_server,
    get_server_users,
    add_server_user,
    edit_server_user,
    delete_server_user,
)
from app.core.auth import (
    get_current_active_user,
    get_current_active_superuser,
    get_current_active_admin,
)
from app.api.utils.tasks import (
    trigger_ansible_hosts,
    trigger_install_gost,
    trigger_server_connect,
    trigger_server_clean,
)

servers_router = r = APIRouter()


@r.get(
    "/servers",
    response_model=t.Union[t.List[ServerOpsOut], t.List[ServerOut]],
    response_model_exclude_none=False,
    response_model_exclude_unset=False,
)
async def servers_list(
    response: Response,
    offset: int = 0,
    limit: int = 100,
    db=Depends(get_db),
    user=Depends(get_current_active_user),
):
    """
    Get all servers
    """
    servers = jsonable_encoder(get_servers(db, user, offset, limit))
    # This is necessary for react-admin to work
    response.headers["Content-Range"] = f"0-9/{len(servers)}"
    if user.is_ops or user.is_superuser:
        return [ServerOpsOut(**server) for server in servers]
    return [ServerOut(**server) for server in servers]


@r.get(
    "/servers/{server_id}",
    response_model=t.Union[ServerOpsOut, ServerOut],
    response_model_exclude_none=True,
)
async def server_get(
    response: Response,
    server_id: int,
    db=Depends(get_db),
    user=Depends(get_current_active_user),
):
    """
    Get server by id
    """
    server = get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    if user.is_admin():
        return ServerOpsOut(**jsonable_encoder(server))
    if not any(user.id == u.id for u in server.allowed_users):
        raise HTTPException(status_code=404, detail="Server not found")
    return ServerOut(**jsonable_encoder(server))


@r.post(
    "/servers", response_model=ServerOpsOut, response_model_exclude_none=True
)
async def server_create(
    request: Request,
    server: ServerCreate,
    db=Depends(get_db),
    user=Depends(get_current_active_admin),
):
    """
    Create a new server
    """
    if server.ansible_host is None:
        server.ansible_host = server.address
    server = create_server(db, server)
    trigger_ansible_hosts()
    trigger_install_gost(server.id)
    trigger_server_connect(server.id)
    return jsonable_encoder(server)


@r.put(
    "/servers/{server_id}",
    response_model=ServerOpsOut,
    response_model_exclude_none=True,
)
async def server_edit(
    request: Request,
    server_id: int,
    server: ServerEdit,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Update an existing server
    """
    server = edit_server(db, server_id, server)
    trigger_ansible_hosts()
    trigger_server_connect(server.id)
    return jsonable_encoder(server)


@r.delete(
    "/servers/{server_id}",
    response_model=ServerOpsOut,
    response_model_exclude_none=True,
)
async def server_delete(
    request: Request,
    server_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Delete an existing server
    """
    server = delete_server(db, server_id)
    trigger_server_clean(server)
    return server


@r.get(
    "/servers/{server_id}/users",
    response_model=t.List[ServerUserOpsOut],
    response_model_exclude_none=True,
)
async def server_users_get(
    response: Response,
    server_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Get server users by id
    """
    server_users = get_server_users(db, server_id)
    return server_users


@r.post(
    "/servers/{server_id}/users",
    response_model=ServerUserOpsOut,
)
async def server_users_add(
    response: Response,
    server_id: int,
    server_user: ServerUserCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Add server user for server
    """
    server_user = add_server_user(db, server_id, server_user)
    return server_user


@r.put(
    "/servers/{server_id}/users",
    response_model=ServerUserOpsOut,
)
async def server_users_edit(
    response: Response,
    server_id: int,
    server_user: ServerUserEdit,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Add server user for server
    """
    server_user = edit_server_user(db, server_id, server_user)
    return server_user


@r.delete(
    "/servers/{server_id}/users/{user_id}",
    response_model=ServerUserOut,
)
async def server_users_delete(
    response: Response,
    server_id: int,
    user_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Delete a server user
    """
    server_user = delete_server_user(db, server_id, user_id)
    return server_user
