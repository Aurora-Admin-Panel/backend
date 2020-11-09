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
from app.db.models.port import Port
from app.db.models.port_forward import MethodEnum, TypeEnum
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
    get_all_gost_rules,
)
from app.db.crud.port import get_port
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
    user=Depends(get_current_active_user),
):
    """
    Get port forward rule
    """
    forward_rule = get_forward_rule(db, server_id, port_id, user)
    if not user.is_admin():
        if not any(
            user.id == u.user_id for u in forward_rule.port.allowed_users
        ):
            raise HTTPException(
                status_code=404, detail="Port forward rule not found"
            )
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
    user=Depends(get_current_active_user),
):
    """
    Create a port forward rule
    """
    db_port = get_port(db, server_id, port_id)
    if not user.is_admin() and not any(
        u.user_id == user.id for u in db_port.allowed_users
    ):
        raise HTTPException(
            status_code=403,
            detail="User not allowed to create forward rule on this port",
        )
    if db_port.forward_rule:
        raise HTTPException(
            status_code=403,
            detail="Cannot create more than one rule on same port",
        )

    if forward_rule.method == MethodEnum.IPTABLES:
        forward_rule = verify_iptables_config(forward_rule)
    elif forward_rule.method == MethodEnum.GOST:
        forward_rule = verify_gost_config(db_port, forward_rule)

    update_gost = False
    if forward_rule.method == MethodEnum.GOST:
        update_gost = len(get_all_gost_rules(db, server_id)) == 0

    forward_rule = create_forward_rule(db, db_port, forward_rule)
    trigger_forward_rule(
        forward_rule,
        forward_rule.port,
        new=forward_rule,
        update_gost=update_gost,
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
    user=Depends(get_current_active_user),
):
    """
    Edit a port forward rule
    """
    db_port = get_port(db, server_id, port_id)
    if not user.is_admin() and not any(
        u.user_id == user.id for u in db_port.allowed_users
    ):
        raise HTTPException(
            status_code=403,
            detail="User not allowed to create forward rule on this port",
        )

    if forward_rule.method == MethodEnum.IPTABLES:
        forward_rule = verify_iptables_config(forward_rule)
    elif forward_rule.method == MethodEnum.GOST:
        forward_rule = verify_gost_config(db_port, forward_rule)

    old, updated = edit_forward_rule(db, server_id, port_id, forward_rule)
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
    forward_rule, port = delete_forward_rule(
        db, server_id, port_id, current_user
    )
    trigger_forward_rule(forward_rule, port, old=forward_rule)
    return forward_rule


def verify_iptables_config(
    rule: t.Union[PortForwardRuleCreate, PortForwardRuleEdit]
) -> t.Union[PortForwardRuleCreate, PortForwardRuleEdit]:
    if not rule.method == MethodEnum.IPTABLES:
        return rule

    if isinstance(rule, PortForwardRuleCreate):
        if not rule.config.get("remote_address") or not rule.config.get(
            "remote_port"
        ):
            raise HTTPException(
                status_code=400,
                detail="Both remote_address and remote_ip are needed",
            )
        if not rule.config.get("type"):
            raise HTTPException(
                status_code=400,
                detail=f"Forward type not specified",
            )

    if rule.config:
        if (
            rule.config.get("type")
            and not rule.config.get("type") in TypeEnum.__members__
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Forward type: {rule.config.get('type')} not supported",
            )
        if not rule.config.get("remote_ip"):
            if rule.config.get("remote_address"):
                if is_ip(rule.config.get("remote_address")):
                    rule.config["remote_ip"] = rule.config.get("remote_address")
                else:
                    rule.config["remote_ip"] = dns_query(
                        rule.config.get("remote_address")
                    )
        elif not is_ip(rule.config.get("remote_ip")):
            raise HTTPException(
                status_code=400,
                detail=f"Not a valid ip address: {rule.config.get('remote_ip')}",
            )
    return rule


def verify_gost_config(
    port: Port, rule: t.Union[PortForwardRuleCreate, PortForwardRuleEdit]
) -> t.Union[PortForwardRuleCreate, PortForwardRuleEdit]:
    if not rule.method == MethodEnum.GOST:
        return rule

    if isinstance(rule, PortForwardRuleCreate):
        if not rule.config.get("ServeNodes") and not rule.config.get(
            "ChainNodes"
        ):
            raise HTTPException(
                status_code=400, detail=f"Bad gost rule: {rule.config}"
            )

    num = port.external_num if port.external_num else port.num
    if rule.config:
        for node in rule.config.get("ServeNodes", []):
            if node.startswith(":"):
                if not node.startswith(f":{num}"):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Port not allowed, ServeNode: {node}",
                    )
            else:
                parsed = urlparse(node)
                if not parsed.netloc.endswith(
                    str(num)
                ) and not parsed.path.endswith(str(num)):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Port not allowed, ServeNode: {node}",
                    )
    return rule