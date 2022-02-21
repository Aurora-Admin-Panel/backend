import typing as t
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload
from urllib.parse import urlparse
from fastapi import HTTPException, status

from app.db.models.user import User
from app.db.models.server import Server
from app.db.schemas.port_forward import (
    PortForwardRuleBase,
    PortForwardRuleOut,
    PortForwardRuleCreate,
    PortForwardRuleEdit,
)
from app.db.models.port import Port, PortUser
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


def get_forward_rule_for_server(
    db: Session, server_id: int
) -> t.List[PortForwardRule]:
    return (
        db.query(PortForwardRule)
        .join(Port)
        .filter(Port.server_id == server_id)
        .options(joinedload(PortForwardRule.port))
        .all()
    )


def get_forward_rule_by_id(db: Session, rule_id: int) -> PortForwardRule:
    return (
        db.query(PortForwardRule)
        .options(joinedload(PortForwardRule.port))
        .filter(PortForwardRule.id == rule_id)
        .first()
    )


def get_forward_rule_for_user(
    db: Session, user_id: int
) -> t.List[PortForwardRule]:
    return (
        db.query(PortForwardRule)
        .join(Port)
        .join(PortUser)
        .join(Server)
        .filter(PortUser.user_id == user_id)
        .all()
    )


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
    return db_forward_rule


def delete_forward_rule(
    db: Session, server_id: int, port_id: int, user: User = None
) -> t.Tuple[PortForwardRule, Port]:
    db_forward_rule = get_forward_rule(db, server_id, port_id)
    if not db_forward_rule:
        raise HTTPException(
            status_code=404, detail="Port forward rule not found"
        )
    if (
        user is not None
        and not user.is_admin()
        and not any(
            user.id == u.user_id for u in db_forward_rule.port.allowed_users
        )
    ):
        raise HTTPException(
            status_code=403,
            detail="User not allowed to delete this port forward rule",
        )
    port = db_forward_rule.port
    db.delete(db_forward_rule)
    db.commit()
    return db_forward_rule, port


def delete_forward_rule_by_id(db: Session, rule_id: int):
    db_forward_rule = get_forward_rule_by_id(db, rule_id)
    if not db_forward_rule:
        return None
    db.delete(db_forward_rule)
    db.commit()
    return db_forward_rule


def get_all_gost_rules(db: Session, server_id: int) -> t.List[PortForwardRule]:
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


def get_all_iptables_rules(db: Session) -> t.List[PortForwardRule]:
    return (
        db.query(PortForwardRule)
        .filter(PortForwardRule.method == MethodEnum.IPTABLES)
        .all()
    )


def get_all_expire_rules(db: Session) -> t.List[PortForwardRule]:
    return filter(
        lambda x: "expire_time" in x.config.keys(),
        db.query(PortForwardRule)
        .options(joinedload(PortForwardRule.port).joinedload(Port.server))
        .all(),
    )


def get_all_ddns_rules(db: Session) -> t.List[PortForwardRule]:
    return (
        db.query(PortForwardRule)
        .options(joinedload(PortForwardRule.port).joinedload(Port.server))
        .filter(
            or_(
                PortForwardRule.method == MethodEnum.IPTABLES,
                PortForwardRule.method == MethodEnum.BROOK,
                PortForwardRule.method == MethodEnum.TINY_PORT_MAPPER,
            )
        )
        .all()
    )


def get_all_non_iptables_rules(db: Session) -> t.List[PortForwardRule]:
    return (
        db.query(PortForwardRule)
        .filter(PortForwardRule.method != MethodEnum.IPTABLES)
        .all()
    )
