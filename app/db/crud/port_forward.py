import typing as t
from sqlalchemy import and_
from sqlalchemy.orm import Session
from urllib.parse import urlparse
from fastapi import HTTPException, status

from app.api.utils.ip import is_ip
from app.api.utils.dns import dns_query
from app.core.security import get_password_hash
from app.db.models.user import User
from app.db.schemas.port_forward import (
    PortForwardRuleBase,
    PortForwardRuleOut,
    PortForwardRuleCreate,
    PortForwardRuleEdit,
)
from app.db.models.port import Port
from app.db.models.port_forward import PortForwardRule, TypeEnum, MethodEnum


def get_forward_rule(
    db: Session, server_id: int, port_id: int, user: User = None
) -> PortForwardRule:
    forward_rule = (
        db.query(PortForwardRule)
        .join(Port)
        .filter(
            and_(
                PortForwardRule.port_id == port_id, Port.server_id == server_id
            )
        )
        .first()
    )
    if user and forward_rule:
        if not user.is_ops and not user.is_superuser:
            if not any(
                user.id == u.user_id for u in forward_rule.port.allowed_users
            ):
                raise HTTPException(
                    status_code=404, detail="Port forward rule not found"
                )
    return forward_rule


def create_forward_rule(
    db: Session, port_id: int, forward_rule: PortForwardRuleCreate, user: User
) -> PortForwardRule:
    port = db.query(Port).filter(Port.id == port_id).first()
    if not user.is_admin() and not any(
        u.user_id == user.id for u in port.allowed_users
    ):
        raise HTTPException(
            status_code=403,
            detail="User not allowed to create forward rule on this port",
        )
    if forward_rule.method == MethodEnum.IPTABLES:
        if not forward_rule.config.get(
            "remote_address"
        ) or not forward_rule.config.get("remote_port"):
            raise HTTPException(
                status_code=401,
                detail="Both remote_address and remote_ip are needed",
            )
        if not forward_rule.config.get("type"):
            raise HTTPException(
                status_code=401,
                detail=f"Forward type not specified",
            )
        forward_rule = verify_iptables_config(forward_rule)
    elif forward_rule.method == MethodEnum.GOST:
        forward_rule = verify_and_replace_port_gost_config(port, forward_rule)

    db_forward_rule = PortForwardRule(
        **forward_rule.dict(), port_id=port_id, status="starting"
    )
    db.add(db_forward_rule)
    db.commit()
    db.refresh(db_forward_rule)
    return db_forward_rule


def edit_forward_rule(
    db: Session,
    server_id: int,
    port_id: int,
    forward_rule: PortForwardRuleEdit,
    user: User,
) -> t.Tuple[PortForwardRuleOut, PortForwardRule]:
    db_forward_rule = get_forward_rule(db, server_id, port_id)
    if not db_forward_rule:
        raise HTTPException(
            status_code=404, detail="Port forward rule not found"
        )
    if not user.is_admin() and not any(
        user.id == u.user_id for u in db_forward_rule.port.allowed_users
    ):
        raise HTTPException(
            status_code=403,
            detail="User not allowed to edit this port forward rule",
        )
    if forward_rule.method == MethodEnum.IPTABLES:
        forward_rule = verify_iptables_config(forward_rule)
    elif forward_rule.method == MethodEnum.GOST:
        forward_rule = verify_and_replace_port_gost_config(
            db_forward_rule.port, forward_rule
        )

    old = PortForwardRuleOut(**db_forward_rule.__dict__)
    updated = forward_rule.dict(exclude_unset=True)
    if db_forward_rule.method == forward_rule.method:
        for key, val in updated["config"].items():
            db_forward_rule.config[key] = val
    else:
        db_forward_rule.config = {}
        for key, val in updated["config"].items():
            db_forward_rule.config[key] = val

    for key, val in updated.items():
        if key == "config":
            continue
        setattr(db_forward_rule, key, val)

    db_forward_rule.status = "starting"
    db.add(db_forward_rule)
    db.commit()
    db.refresh(db_forward_rule)
    return old, db_forward_rule


def delete_forward_rule(
    db: Session, server_id: int, port_id: int, user: User
) -> t.Tuple[PortForwardRule, Port]:
    db_forward_rule = get_forward_rule(db, server_id, port_id)
    if not db_forward_rule:
        raise HTTPException(
            status_code=404, detail="Port forward rule not found"
        )
    if not user.is_admin() and not any(
        user.id == u.user_id for u in db_forward_rule.port.allowed_users
    ):
        raise HTTPException(
            status_code=403,
            detail="User not allowed to delete this port forward rule",
        )
    port = db_forward_rule.port
    db.delete(db_forward_rule)
    db.commit()
    return db_forward_rule, port


def verify_iptables_config(
    rule: t.Union[PortForwardRuleCreate, PortForwardRuleEdit]
) -> t.Union[PortForwardRuleCreate, PortForwardRuleEdit]:
    if not rule.method == MethodEnum.IPTABLES:
        return rule

    if rule.config:
        if (
            rule.config.get("type")
            and not rule.config.get("type") in TypeEnum.__members__
        ):
            raise HTTPException(
                status_code=401,
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
                status_code=401,
                detail=f"Not a valid ip address: {rule.config.get('remote_ip')}",
            )
    return rule


def verify_and_replace_port_gost_config(
    port: Port, rule: t.Union[PortForwardRuleCreate, PortForwardRuleEdit]
) -> t.Union[PortForwardRuleCreate, PortForwardRuleEdit]:
    if not rule.method == MethodEnum.GOST:
        return rule
    serve_nodes = []
    if rule.config:
        for node in rule.config.get("ServeNodes", []):
            if node.startswith(":"):
                if not node.startswith(f":{port.num}"):
                    raise HTTPException(
                        status_code=401,
                        detail=f"Port not allowed, ServeNode: {node}",
                    )
            else:
                parsed = urlparse(node)
                if not parsed.netloc.endswith(
                    str(port.num)
                ) and not parsed.path.endswith(str(port.num)):
                    raise HTTPException(
                        status_code=401,
                        detail=f"Port not allowed, ServeNode: {node}",
                    )
            serve_nodes.append(
                node.replace(f":{port.num}", f":{port.internal_num}")
            )
        rule.config["ServeNodes"] = serve_nodes
    return rule


def get_all_gost_rules(db: Session, server_id: int) -> bool:
    return (
        db.query(PortForwardRule)
        .join(Port)
        .filter(
            and_(
                PortForwardRule.method == MethodEnum.GOST,
                Port.server_id == server_id,
            )
        )
        .all()
    )
