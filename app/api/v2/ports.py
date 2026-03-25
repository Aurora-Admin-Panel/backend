import typing as t

from app.core.auth import (
    get_current_active_admin,
    get_current_active_superuser,
    get_current_active_user,
)
from app.db.crud.port import (
    add_port_user,
    create_port,
    delete_port,
    delete_port_user,
    edit_port,
    edit_port_user,
    get_port,
    get_port_users,
    get_ports,
)
from app.db.crud.port_forward import delete_forward_rule
from app.db.crud.port_usage import create_port_usage, edit_port_usage
from app.db.crud.user import get_user
from app.db.schemas.port import (
    PortCreate,
    PortEdit,
    PortEditBase,
    PortOpsOut,
    PortOut,
    PortUserCreate,
    PortUserEdit,
    PortUserOpsOut,
    PortUserOut,
)
from app.db.schemas.port_usage import (
    PortUsageCreate,
    PortUsageEdit,
    PortUsageOut,
)
from app.db.session import get_db
from app.utils.tasks import (
    remove_tc,
    trigger_iptables_reset,
    trigger_port_clean,
    trigger_tc,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    encoders,
)
from fastapi.encoders import jsonable_encoder
from fastapi_pagination import Page, add_pagination, paginate

ports_v2_router = r = APIRouter()


@r.get(
    "/servers/{server_id}/ports",
    response_model=Page[PortOut],
    response_model_exclude_none=False,
)
async def ports_list(
    response: Response,
    server_id: int,
    db=Depends(get_db),
    user=Depends(get_current_active_user),
):
    """
    Get all ports on one server
    """
    return paginate(get_ports(db, server_id, user))


add_pagination(ports_v2_router)
