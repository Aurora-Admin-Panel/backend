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
    PortUserCreate,
    PortUserEdit,
    PortUserOut,
    PortUserOpsOut,
)
from app.db.schemas.port_usage import (
    PortUsageEdit,
    PortUsageOut,
    PortUsageCreate,
)
from app.db.crud.port import (
    get_ports,
    get_port,
    create_port,
    edit_port,
    delete_port,
    get_port_users,
    add_port_user,
    edit_port_user,
    delete_port_user,
)
from app.db.crud.port_usage import create_port_usage, edit_port_usage
from app.db.crud.port_forward import delete_forward_rule
from app.db.crud.user import get_user
from app.core.auth import (
    get_current_active_user,
    get_current_active_superuser,
    get_current_active_admin,
)
from app.api.utils.tasks import (
    trigger_tc,
    remove_tc,
    trigger_forward_rule,
    trigger_iptables_reset,
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
    if not port:
        raise HTTPException(status_code=404, detail="Port not found")

    if user.is_admin():
        return PortOpsOut(**jsonable_encoder(port))
    if not any(user.id == u["user_id"] for u in port.allowed_users):
        raise HTTPException(status_code=404, detail="Port not found")
    return PortOut(**jsonable_encoder(port))


@r.post(
    "/servers/{server_id}/ports",
    response_model=PortOpsOut,
    response_model_exclude_none=True,
)
async def port_create(
    request: Request,
    server_id: int,
    port: PortCreate,
    db=Depends(get_db),
    user=Depends(get_current_active_admin),
):
    """
    Create a new port on server
    """
    db_port = create_port(db, server_id, port)
    trigger_tc(db_port)
    return db_port


@r.put(
    "/servers/{server_id}/ports/{port_id}",
    response_model=PortOpsOut,
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
    db_port = edit_port(db, server_id, port_id, port)
    trigger_tc(db_port)
    return db_port


@r.delete(
    "/servers/{server_id}/ports/{port_id}",
    response_model=PortOpsOut,
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
    db_port = get_port(db, server_id, port_id)
    if db_port:
        if db_port.forward_rule:
            trigger_forward_rule(
                db_port.forward_rule, db_port, old=db_port.forward_rule
            )
        delete_port(db, server_id, port_id)
    remove_tc(server_id, db_port.num)
    return db_port


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
    response_model=PortUserOpsOut,
)
async def port_user_add(
    request: Request,
    server_id: int,
    port_id: int,
    port_user: PortUserCreate,
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
    return jsonable_encoder(port_user)


@r.put(
    "/servers/{server_id}/ports/{port_id}/users/{user_id}",
    response_model=PortUserOpsOut,
)
async def port_user_edit(
    request: Request,
    server_id: int,
    port_id: int,
    user_id: int,
    port_user: PortUserEdit,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Add a port user to port
    """
    port_user = edit_port_user(db, server_id, port_id, user_id, port_user)
    if not port_user:
        raise HTTPException(status_code=400, detail="Port user not found")
    return jsonable_encoder(port_user)


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


@r.post(
    "/servers/{server_id}/ports/{port_id}/usage",
    response_model=PortUsageOut,
)
async def port_usage_edit(
    server_id: int,
    port_id: int,
    port_usage: PortUsageEdit,
    db=Depends(get_db),
    user=Depends(get_current_active_admin),
):
    """
    Update a port usage
    """
    db_port_usage = edit_port_usage(db, port_id, port_usage)
    if (
        db_port_usage
        and sum(
            [
                port_usage.download,
                port_usage.upload,
                port_usage.download_accumulate,
                port_usage.upload_accumulate,
            ]
        )
        == 0
    ):
        trigger_iptables_reset(db_port_usage.port)
    return db_port_usage
