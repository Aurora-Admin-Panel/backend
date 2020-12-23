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
from app.utils.ip import is_ip
from app.utils.dns import dns_query
from app.utils.tasks import trigger_forward_rule, trigger_port_clean
from app.db.models.port import Port
from app.db.models.port_forward import MethodEnum, TypeEnum
from app.db.schemas.port_forward import (
    PortForwardRuleCreate,
    PortForwardRuleEdit,
    PortForwardRuleOut,
    PortForwardRuleArtifacts,
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
    if not forward_rule:
        raise HTTPException(
            status_code=404, detail="Port forward rule not found"
        )
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

    forward_rule = create_forward_rule(db, db_port, forward_rule)
    trigger_forward_rule(
        forward_rule,
        forward_rule.port,
        new=forward_rule,
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
    print(f"{forward_rule.method.value}_disabled")
    if db_port.server.config.get(f"{forward_rule.method.value}_disabled"):
        raise HTTPException(
            status_code=403,
            detail=f"{forward_rule.method.value} is not allowed")

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
    trigger_port_clean(port.server, port)
    return forward_rule


@r.get(
    "/servers/{server_id}/ports/{port_id}/forward_rule/artifacts",
    response_model=PortForwardRuleArtifacts,
)
async def forward_rule_runner_get(
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
    if not forward_rule:
        raise HTTPException(
            status_code=404, detail="Port forward rule not found"
        )
    if not user.is_admin():
        if not any(
            user.id == u.user_id for u in forward_rule.port.allowed_users
        ):
            raise HTTPException(
                status_code=404, detail="Port forward rule not found"
            )
    artifacts = PortForwardRuleArtifacts()
    if forward_rule.config.get('runner'):
        with open(f"ansible/priv_data_dirs/{server_id}/artifacts/{forward_rule.config.get('runner')}/stdout", 'r') as f:
            artifacts.stdout = f.read()
    return artifacts


def verify_iptables_config(
    rule: t.Union[PortForwardRuleCreate, PortForwardRuleEdit]
) -> t.Union[PortForwardRuleCreate, PortForwardRuleEdit]:
    if not rule.method == MethodEnum.IPTABLES:
        return rule
    if rule.config:
        if not rule.config.remote_ip:
            if rule.config.remote_address:
                if is_ip(rule.config.remote_address):
                    rule.config.remote_ip = rule.config.remote_address
                else:
                    rule.config.remote_ip = dns_query(
                        rule.config.remote_address
                    )
        elif not is_ip(rule.config.remote_ip):
            raise HTTPException(
                status_code=400,
                detail=f"Not a valid ip address: {rule.config.remote_ip}",
            )
    return rule


def verify_gost_config(
    port: Port, rule: t.Union[PortForwardRuleCreate, PortForwardRuleEdit]
) -> t.Union[PortForwardRuleCreate, PortForwardRuleEdit]:
    if not rule.method == MethodEnum.GOST:
        return rule

    num = port.external_num if port.external_num else port.num
    for node in rule.config.ServeNodes:
        if node.startswith(":"):
            if not node.startswith(f":{num}"):
                raise HTTPException(
                    status_code=403,
                    detail=f"Port not allowed, ServeNode: {node}",
                )
        else:
            parsed = urlparse(node)
            if not parsed.netloc.endswith(str(num)) \
                and not parsed.path.endswith(str(num)):
                raise HTTPException(
                    status_code=403,
                    detail=f"Port not allowed, ServeNode: {node}",
                )
    return rule