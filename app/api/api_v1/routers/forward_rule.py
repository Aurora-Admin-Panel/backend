import typing as t
from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Depends,
    Response,
    encoders,
)
from urllib.parse import urlparse

from app.db.session import get_db
from app.api.utils.ip import is_ip
from app.api.utils.dns import dns_query
from app.api.utils.tasks import trigger_forward_rule
from app.db.models.port_forward import MethodEnum
from app.db.schemas.port_forward import (
    PortForwardRuleCreate,
    PortForwardRuleEdit,
    PortForwardRuleOut,
)
from app.db.crud.port_forward import (
    get_forward_rule,
    create_forward_rule,
    edit_forward_rule,
    delete_forward_rule,
)
from app.core.auth import (
    get_current_active_user,
    get_current_active_superuser,
    get_current_active_admin,
)

forward_rule_router = r = APIRouter()


@r.get(
    "/servers/{server_id}/ports/{port_id}/forward_rule",
    response_model=PortForwardRuleOut,
)
async def forward_rule_get(
    response: Response,
    server_id: int,
    port_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Get port forward rule
    """
    forward_rule = get_forward_rule(db, server_id, port_id, current_user)
    if forward_rule and forward_rule.method == MethodEnum.GOST:
        forward_rule.config["ServeNodes"] = [
            n.replace(
                f":{forward_rule.port.internal_num}",
                f":{forward_rule.port.num}",
            )
            for n in forward_rule.config.get("ServeNodes", [])
        ]
    return forward_rule


@r.post(
    "/servers/{server_id}/ports/{port_id}/forward_rule",
    response_model=PortForwardRuleOut,
)
async def forward_rule_create(
    response: Response,
    server_id: int,
    port_id: int,
    forward_rule: PortForwardRuleCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Create a port forward rule
    """
    forward_rule, update_gost = create_forward_rule(
        db, port_id, forward_rule, current_user
    )

    trigger_forward_rule(
        forward_rule, forward_rule.port, new=forward_rule, update_gost=update_gost
    )
    return forward_rule


@r.put(
    "/servers/{server_id}/ports/{port_id}/forward_rule",
    response_model=PortForwardRuleOut,
)
async def forward_rule_edit(
    response: Response,
    server_id: int,
    port_id: int,
    forward_rule: PortForwardRuleEdit,
    db=Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Edit a port forward rule
    """
    old, updated = edit_forward_rule(
        db, server_id, port_id, forward_rule, current_user
    )
    trigger_forward_rule(updated, updated.port, old, updated)
    return updated


@r.delete(
    "/servers/{server_id}/ports/{port_id}/forward_rule",
    response_model=PortForwardRuleOut,
)
async def forward_rule_delete(
    response: Response,
    server_id: int,
    port_id: int,
    db=Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Delete a port forward rule
    """
    forward_rule, port = delete_forward_rule(db, server_id, port_id, current_user)
    trigger_forward_rule(forward_rule, port, old=forward_rule)
    return forward_rule