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
from app.api.utils.ip import is_ip
from app.api.utils.dns import dns_query
from app.api.utils.iptables import trigger_forward_rule
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
    if not forward_rule.remote_ip:
        if not is_ip(forward_rule.remote_address):
            forward_rule.remote_ip = dns_query(forward_rule.remote_address)
        else:
            forward_rule.remote_ip = forward_rule.remote_address
    forward_rule = create_forward_rule(db, port_id, forward_rule, current_user)

    trigger_forward_rule(forward_rule, new = forward_rule)
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
    if not forward_rule.remote_ip:
        if not is_ip(forward_rule.remote_address):
            forward_rule.remote_ip = dns_query(forward_rule.remote_address)
        else:
            forward_rule.remote_ip = forward_rule.remote_address
    old, updated = edit_forward_rule(
        db, server_id, port_id, forward_rule, current_user
    )
    trigger_forward_rule(updated, old, updated)
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
    forward_rule = delete_forward_rule(db, server_id, port_id, current_user)
    trigger_forward_rule(forward_rule, old = forward_rule)
    return forward_rule