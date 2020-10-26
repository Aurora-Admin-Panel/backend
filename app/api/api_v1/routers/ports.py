import typing as t
from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Depends,
    Response,
    encoders,
)

from app.db.session import get_db
from app.db.schemas.port import (
    Port,
    PortOut,
    PortOpsOut,
    PortCreate,
    PortEdit,
    PortUserEdit,
    PortUserOut,
)
from app.db.crud.port import (
    get_ports,
    get_port,
    create_port,
    edit_port,
    delete_port,
    get_port_users,
    add_port_user,
    delete_port_user,
)
from app.core.auth import (
    get_current_active_user,
    get_current_active_superuser,
    get_current_active_admin,
)

ports_router = r = APIRouter()


@r.get(
    "/servers/{server_id}/ports",
    response_model=t.Union[t.List[PortOpsOut], t.List[PortOut]],
    response_model_exclude_none=False,
)
async def ports_list(
    response: Response,
    server_id: int,
    offset: int = 0,
    limit: int = 100,
    db=Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Get all ports related to server
    """
    ports = get_ports(db, server_id, current_user, offset, limit)
    # This is necessary for react-admin to work
    response.headers["Content-Range"] = f"0-9/{len(ports)}"
    print(ports)
    return ports


@r.get(
    "/servers/{server_id}/ports/{port_id}",
    response_model=t.Union[PortOpsOut, PortOut],
    response_model_exclude_none=False,
    response_model_exclude_unset=False,
)
async def port_get(
    response: Response,
    server_id: int,
    port_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Get port by id
    """
    port = get_port(db, server_id, port_id, current_user)
    return port


@r.post(
    "/servers/{server_id}/ports",
    response_model=Port,
    response_model_exclude_none=True,
)
async def port_create(
    request: Request,
    server_id: int,
    port: PortCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Create a new port on server
    """
    if port.internal_num is None:
        port.internal_num = port.num
    return create_port(db, server_id, port)


@r.put(
    "/servers/{server_id}/ports/{port_id}",
    response_model=Port,
    response_model_exclude_none=True,
)
async def port_edit(
    request: Request,
    server_id: int,
    port_id: int,
    port: PortEdit,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Update an existing port
    """
    return edit_port(db, server_id, port_id, port)


@r.delete(
    "/servers/{server_id}/ports/{port_id}",
    response_model=Port,
    response_model_exclude_none=True,
)
async def port_delete(
    request: Request,
    server_id: int,
    port_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Delete an existing port on server
    """
    return delete_port(db, server_id, port_id)


@r.get(
    "/servers/{server_id}/ports/{port_id}/users",
    response_model=t.List[PortUserOut],
)
async def port_users_get(
    request: Request,
    server_id: int,
    port_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Get all port users
    """
    port_users = get_port_users(db, server_id, port_id)
    return port_users


@r.post(
    "/servers/{server_id}/ports/{port_id}/users",
    response_model=PortUserOut,
)
async def port_user_add(
    request: Request,
    server_id: int,
    port_id: int,
    port_user: PortUserEdit,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Add a port user to port
    """
    port_user = add_port_user(db, server_id, port_id, port_user)
    return port_user


@r.delete(
    "/servers/{server_id}/ports/{port_id}/users/{user_id}",
    response_model=PortUserOut,
)
async def port_users_delete(
    request: Request,
    server_id: int,
    port_id: int,
    user_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Delete a port user for port
    """
    port_user = delete_port_user(db, server_id, port_id, user_id)
    return port_user