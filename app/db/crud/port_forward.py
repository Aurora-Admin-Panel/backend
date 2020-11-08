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
    return forward_rule


def create_forward_rule(
    db: Session, port: Port, forward_rule: PortForwardRuleCreate
) -> PortForwardRule:
    db_forward_rule = PortForwardRule(
        **forward_rule.dict(), port_id=port.id, status="starting"
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
) -> t.Tuple[PortForwardRuleOut, PortForwardRule]:
    db_forward_rule = get_forward_rule(db, server_id, port_id)
    if not db_forward_rule:
        raise HTTPException(
            status_code=404, detail="Port forward rule not found"
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
