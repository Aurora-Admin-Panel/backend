import typing as t
from sqlalchemy import and_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.security import get_password_hash
from app.db.models.user import User
from app.db.schemas.port_forward import (
    PortForwardRuleOut,
    PortForwardRuleCreate,
    PortForwardRuleEdit,
)
from app.db.models.port import Port
from app.db.models.port_forward import PortForwardRule


def get_forward_rule(
    db: Session, server_id: int, port_id: int, user: User = None
) -> PortForwardRuleOut:
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
    if not user.is_admin() and not any(u.user_id == user.id for u in port.allowed_users):
        raise HTTPException(
            status_code=403,
            detail="User not allowed to create forward rule on this port",
        )
    if port.port_forward_rules:
        raise HTTPException(
            status_code=403,
            detail="Cannot create multiple forward rules on same port",
        )
    db_forward_rule = PortForwardRule(**forward_rule.dict(), port_id=port_id, status="starting")
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

    old = PortForwardRuleOut(**db_forward_rule.__dict__)
    updated = forward_rule.dict(exclude_unset=True)
    for key, val in updated.items():
        setattr(db_forward_rule, key, val)
    db_forward_rule.status = "starting"

    db.add(db_forward_rule)
    db.commit()
    db.refresh(db_forward_rule)
    return old, db_forward_rule


def delete_forward_rule(
    db: Session, server_id: int, port_id: int, user: User
) -> PortForwardRule:
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
    db.delete(db_forward_rule)
    db.commit()
    return db_forward_rule
