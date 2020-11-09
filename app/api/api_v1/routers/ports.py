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
from app.db.schemas.port import (
    PortOut,
    PortOpsOut,
    PortCreate,
    PortEdit,
    PortUserEdit,
    PortUserOut,
    PortUserOpsOut,
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
from app.db.crud.user import get_user
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
    user=Depends(get_current_active_user),
):
    """
    Get all ports related to server
    """
    ports = get_ports(db, server_id, user, offset, limit)
    ports = jsonable_encoder(ports)
    # This is necessary for react-admin to work
    response.headers["Content-Range"] = f"0-9/{len(ports)}"

    if user.is_admin():
        return [PortOpsOut(**port) for port in ports]
    return [PortOut(**port) for port in ports]


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
    user=Depends(get_current_active_user),
):
    """
    Get port by id
    """
    port = get_port(db, server_id, port_id)

    if user.is_admin():
        return PortOpsOut(**jsonable_encoder(port))
    if not any(user.id == u["user_id"] for u in port.allowed_users):
        raise HTTPException(status_code=404, detail="Port not found")
    return PortOut(**jsonable_encoder(port))


@r.post(
    "/servers/{server_id}/ports",
    response_model=PortOut,
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
    return create_port(db, server_id, port)


@r.put(
    "/servers/{server_id}/ports/{port_id}",
    response_model=PortOut,
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
    response_model=PortOut,
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
    response_model=t.List[PortUserOpsOut],
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
    return jsonable_encoder(port_users)


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
    db_user = get_user(db, port_user.user_id)
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found")
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