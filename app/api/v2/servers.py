import typing as t
from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Depends,
    Response,
    encoders,
)
from fastapi_pagination import pagination_params, Page
from fastapi_pagination.paginator import paginate

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
    trigger_server_connect,
    trigger_server_clean,
)

servers_v2_router = r = APIRouter()


@r.get(
    "/servers",
    response_model=Page[ServerOut],
    response_model_exclude_none=False,
    response_model_exclude_unset=False,
    dependencies=[Depends(pagination_params)],
)
async def servers_list(
    response: Response,
    db=Depends(get_db),
    user=Depends(get_current_active_user),
):
    """
    Get all servers
    """
    return paginate(get_servers(db, user))


@r.get(
    "/servers/{server_id}",
    response_model=ServerOut,
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
    if not user.is_superuser and not any(
        user.id == u.user_id for u in server.allowed_users
    ):
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@r.get(
    "/servers/{server_id}/detailed",
    response_model=ServerOpsOut,
    response_model_exclude_none=True,
)
async def detailed_server_get(
    response: Response,
    server_id: int,
    db=Depends(get_db),
    user=Depends(get_current_active_user),
):
    """
    Get detailed server by id
    """
    server = get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    if (
        not user.is_superuser
        and not user.is_ops
        and not any(user.id == u.user_id for u in server.allowed_users)
    ):
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@r.get(
    "/servers/{server_id}/users",
    response_model=Page[ServerUserOpsOut],
    response_model_exclude_none=True,
    dependencies=[Depends(pagination_params)],
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
        return paginate(get_server_users_for_ops(db, server_id))
    return paginate(get_server_users(db, server_id))
