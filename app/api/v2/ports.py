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
from fastapi_pagination import pagination_params, Page
from fastapi_pagination.paginator import paginate

from app.db.session import get_db
from app.db.schemas.port import (
    PortOut,
    PortOpsOut,
    PortCreate,
    PortEdit,
    PortEditBase,
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
from app.utils.tasks import (
    trigger_tc,
    remove_tc,
    trigger_iptables_reset,
    trigger_port_clean,
)

ports_v2_router = r = APIRouter()


@r.get(
    "/servers/{server_id}/ports",
    response_model=Page[PortOut],
    response_model_exclude_none=False,
    dependencies=[Depends(pagination_params)],
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
