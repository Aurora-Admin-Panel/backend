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
    ServerConnectArg,
    ServerCreate,
    ServerEdit,
    ServerConfigEdit,
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
    edit_server_config,
    delete_server,
    get_server_users,
    get_server_users_for_ops,
    add_server_user,
    edit_server_user,
    delete_server_user,
)
from app.core.auth import (
    get_current_active_user,
    get_current_active_superuser,
    get_current_active_admin,
)
from app.utils.tasks import (
    trigger_ansible_hosts,
    trigger_server_init,
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
    servers = get_servers(db, user)
    return servers


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
        return ServerOpsOut(**server.__dict__)
    if not any(user.id == u.user_id for u in server.allowed_users):
        raise HTTPException(status_code=404, detail="Server not found")
    return ServerOut(**server.__dict__)


@r.post(
    "/servers", response_model=ServerOut, response_model_exclude_none=True
)
async def server_create(
    request: Request,
    server: ServerCreate,
    db=Depends(get_db),
    user=Depends(get_current_active_superuser),
):
    """
    Create a new server
    """
    if server.ansible_host is None:
        server.ansible_host = server.address
    if server.ssh_password:
        server.ssh_password = server.ssh_password.replace("\\", "\\\\")
        server.ssh_password = server.ssh_password.replace('"', '\\"')
    if server.sudo_password:
        server.sudo_password = server.sudo_password.replace("\\", "\\\\")
        server.sudo_password = server.sudo_password.replace('"', '\\"')

    server = create_server(db, server)
    if not server or not server.id:
        raise HTTPException(status_code=400, detail="Server creation failed")
    trigger_ansible_hosts()
    trigger_server_init(server.id, init=True)
    return server


@r.put(
    "/servers/{server_id}",
    response_model=ServerOut,
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
    # TODO: Disallow unauthorized ops to edit server
    if server.ssh_password:
        server.ssh_password = server.ssh_password.replace("\\", "\\\\")
        server.ssh_password = server.ssh_password.replace('"', '\\"')
    if server.sudo_password:
        server.sudo_password = server.sudo_password.replace("\\", "\\\\")
        server.sudo_password = server.sudo_password.replace('"', '\\"')
    server = edit_server(db, server_id, server)
    trigger_ansible_hosts()
    if server.config["system"] is None:
        trigger_server_init(server.id)
    return server


@r.put(
    "/servers/{server_id}/config",
    response_model=ServerOpsOut,
    response_model_exclude_none=True,
)
async def server_config_edit(
    request: Request,
    server_id: int,
    server: ServerConfigEdit,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Update an existing server
    """
    return edit_server_config(db, server_id, server)


@r.delete(
    "/servers/{server_id}",
    response_model=ServerOpsOut,
    response_model_exclude_none=True,
)
async def server_delete(
    request: Request,
    server_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_active_superuser),
):
    """
    Delete an existing server
    """
    server = delete_server(db, server_id)
    trigger_server_clean(server)
    return server


@r.post(
    "/servers/{server_id}/connect",
    response_model=ServerOut,
    response_model_exclude_none=True,
)
async def server_connect(
    request: Request,
    server_id: int,
    connect_arg: ServerConnectArg,
    db=Depends(get_db),
    user=Depends(get_current_active_user),
):
    """
    Connects a server and update something
    """
    if not user.is_admin() and connect_arg.dict(exclude_defaults=True):
        raise HTTPException(status_code=403, detail="Not authorized")
    server = edit_server(db, server_id, ServerEdit(), reset_system=True)
    trigger_server_connect(server.id)
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
    if current_user.is_ops:
        return get_server_users_for_ops(db, server_id)
    return get_server_users(db, server_id)


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
    "/servers/{server_id}/users/{user_id}",
    response_model=ServerUserOpsOut,
)
async def server_users_edit(
    response: Response,
    server_id: int,
    user_id: int,
    server_user: ServerUserEdit,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Add server user for server
    """
    server_user = edit_server_user(db, server_id, user_id, server_user)
    if not server_user:
        raise HTTPException(status_code=404, detail="Server user not found")
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
