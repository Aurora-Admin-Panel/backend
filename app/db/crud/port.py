import typing as t
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from .server import add_server_user
from app.db.schemas.user import User
from app.db.schemas.server import ServerUserCreate
from app.db.schemas.port import (
    PortBase,
    PortCreate,
    PortEdit,
    PortOut,
    PortOpsOut,
    PortUserEdit,
    PortUserOut,
    PortUserCreate,
)
from app.db.models.server import Server, ServerUser
from app.db.models.port import Port, PortUser
from app.db.models.port_forward import PortForwardRule


def get_ports(
    db: Session, server_id: int, user: User
) -> t.List[Port]:
    if user.is_admin():
        return (
            db.query(Port)
            .filter(Port.server_id == server_id)
            .options(joinedload(Port.allowed_users).joinedload(PortUser.user))
            .options(joinedload(Port.forward_rule))
            .options(joinedload(Port.usage))
            .order_by(Port.num)
            .all()
        )
    return (
        db.query(Port)
        .filter(
            and_(
                Port.server_id == server_id,
                Port.allowed_users.any(user_id=user.id),
            )
        )
        .options(joinedload(Port.allowed_users).joinedload(PortUser.user))
        .options(joinedload(Port.forward_rule))
        .options(joinedload(Port.usage))
        .order_by(Port.num)
        .all()
    )


def get_port(db: Session, server_id: int, port_id: int) -> Port:
    return (
        db.query(Port)
        .filter(and_(Port.server_id == server_id, Port.id == port_id))
        .options(joinedload(Port.allowed_users).joinedload(PortUser.user))
        .options(joinedload(Port.forward_rule))
        .options(joinedload(Port.usage))
        .first()
    )


def get_port_with_num(db: Session, server_id: int, port_num: int) -> Port:
    return (
        db.query(Port)
        .filter(and_(Port.server_id == server_id, Port.num == port_num))
        .options(joinedload(Port.usage))
        .first()
    )


def get_port_by_id(db: Session, port_id: int) -> Port:
    return (
        db.query(Port)
        .filter(Port.id == port_id)
        .options(joinedload(Port.forward_rule))
        .first()
    )


def create_port(db: Session, server_id: int, port: PortCreate) -> Port:
    db_port = Port(**port.dict(), server_id=server_id)
    db.add(db_port)
    db.commit()
    db.refresh(db_port)
    return get_port(db, server_id, db_port.id)


def edit_port(
    db: Session, db_port: Port, port: PortEdit
) -> Port:
    updated = port.dict(exclude_unset=True)
    for key, val in updated.items():
        setattr(db_port, key, val)

    db.add(db_port)
    db.commit()
    db.refresh(db_port)
    return db_port


def delete_port(db: Session, server_id: int, port_id: int) -> PortOut:
    db_port = get_port(db, server_id, port_id)
    if not db_port:
        raise HTTPException(status_code=404, detail="Port not found")
    db.delete(db_port)
    db.commit()
    return db_port


def get_port_users(
    db: Session, server_id: int, port_id: int
) -> t.List[PortUser]:
    port_users = (
        db.query(PortUser)
        .filter(and_(Port.server_id == server_id, PortUser.port_id == port_id))
        .options(joinedload(PortUser.user))
        .all()
    )
    return port_users


def get_port_user(
    db: Session, server_id: int, port_id: int, user_id: int,
) -> PortUser:
    return (
        db.query(PortUser)
        .filter(and_(Port.server_id == server_id, PortUser.port_id == port_id, PortUser.user_id == user_id))
        .options(joinedload(PortUser.user))
        .first()
    )


def add_port_user(
    db: Session, server_id: int, port_id: int, port_user: PortUserCreate
) -> PortUser:
    db_port_user = PortUser(
        **port_user.dict(exclude_unset=True), port_id=port_id
    )
    db.add(db_port_user)
    db.commit()
    db.refresh(db_port_user)

    db_server_user = (
        db.query(ServerUser)
        .filter(
            and_(
                ServerUser.server_id == server_id,
                ServerUser.user_id == port_user.user_id,
            )
        )
        .first()
    )
    if not db_server_user:
        add_server_user(
            db, server_id, ServerUserCreate(user_id=port_user.user_id)
        )
    return get_port_user(db, server_id, port_id, port_user.user_id)


def edit_port_user(
    db: Session, server_id: int, port_id: int, user_id: int, port_user: PortUserEdit
) -> PortUser:
    db_port_user = get_port_user(db, server_id, port_id, user_id)
    if not db_port_user:
        return db_port_user

    updated = port_user.dict(exclude_unset=True)
    for key, val in updated.items():
        setattr(db_port_user, key, val)
    db.add(db_port_user)
    db.commit()
    return get_port_user(db, server_id, port_id, user_id)


def delete_port_user(
    db: Session, server_id: int, port_id: int, user_id: int
) -> PortUser:
    db_port_user = (
        db.query(PortUser)
        .filter(and_(PortUser.port_id == port_id, PortUser.user_id == user_id))
        .first()
    )
    db.delete(db_port_user)
    db.commit()
    return db_port_user
