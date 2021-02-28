import typing as t
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from app.db.models.user import User
from app.db.schemas.server import (
    ServerCreate,
    ServerEdit,
    ServerConfigEdit,
    ServerUserEdit,
    ServerUserCreate,
)
from app.db.models.server import Server, ServerUser
from app.db.models.port import Port


def get_servers(db: Session, user: User = None) -> t.List[Server]:
    # Only superuser can see all the servers.
    if not user or user.is_superuser:
        return (
            db.query(Server)
            .filter(Server.is_active == True)
            .options(joinedload(Server.ports).joinedload(Port.allowed_users))
            .order_by(Server.name)
            .all()
        )
    return (
        db.query(Server)
        .filter(
            and_(
                Server.is_active == True,
                Server.allowed_users.any(user_id=user.id),
            )
        )
        .options(joinedload(Server.ports).joinedload(Port.allowed_users))
        .order_by(Server.name)
        .all()
    )


def get_server(db: Session, server_id: int) -> Server:
    return (
        db.query(Server)
        .filter(and_(Server.id == server_id, Server.is_active == True))
        .options(joinedload(Server.ports).joinedload(Port.allowed_users))
        .first()
    )


def get_server_with_ports_usage(db: Session, server_id: int) -> Server:
    return (
        db.query(Server)
        .filter(and_(Server.id == server_id, Server.is_active == True))
        .options(joinedload(Server.ports).joinedload(Port.usage))
        .first()
    )


def create_server(db: Session, server: ServerCreate) -> Server:
    db_server = Server(**server.dict())
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    return db_server


def edit_server(
    db: Session, server_id: int, server: ServerEdit, reset_system: bool = False
) -> Server:
    db_server = get_server(db, server_id)
    if not db_server:
        raise HTTPException(status_code=404, detail="Server not found")
    updated = server.dict(exclude_unset=True)

    for key, val in updated.items():
        setattr(db_server, key, val)
    if (
        reset_system
        or server.sudo_password
        or server.ssh_password
        or server.ansible_host
        or server.ansible_user
        or server.ansible_port
    ):
        db_server.config["system"] = None

    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    return get_server(db, db_server.id)


def edit_server_config(
    db: Session, server_id: int, config: ServerConfigEdit
) -> Server:
    db_server = get_server(db, server_id)
    if not db_server:
        raise HTTPException(status_code=404, detail="Server not found")

    for key, val in config.dict(exclude_unset=True).items():
        db_server.config[key] = val

    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    return get_server(db, db_server.id)


def delete_server(db: Session, server_id: int) -> Server:
    db_server = get_server(db, server_id)
    if not db_server:
        raise HTTPException(status_code=404, detail="Server not found")
    db.delete(db_server)
    db.commit()
    return db_server


def get_server_users(db: Session, server_id: int) -> t.List[ServerUser]:
    server_users = (
        db.query(ServerUser)
        .filter(ServerUser.server_id == server_id)
        .options(joinedload(ServerUser.user))
        .all()
    )
    return server_users


def get_server_users_for_ops(db: Session, server_id: int) -> t.List[ServerUser]:
    server_users = (
        db.query(ServerUser)
        .join(User)
        .filter(ServerUser.server_id == server_id)
        .filter(User.is_ops == False)
        .options(joinedload(ServerUser.user))
        .all()
    )
    return server_users


def get_server_user(db: Session, server_id: int, user_id: int) -> ServerUser:
    return (
        db.query(ServerUser)
        .filter(
            and_(
                ServerUser.server_id == server_id, ServerUser.user_id == user_id
            )
        )
        .options(joinedload(ServerUser.user))
        .first()
    )


def add_server_user(
    db: Session, server_id: int, server_user: ServerUserCreate
) -> ServerUser:
    db_server_user = ServerUser(
        **server_user.dict(exclude_unset=True), server_id=server_id
    )
    db.add(db_server_user)
    db.commit()
    db.refresh(db_server_user)
    return db_server_user


def edit_server_user(
    db: Session, server_id: int, user_id: int, server_user: ServerUserEdit
) -> ServerUser:
    db_server_user = get_server_user(db, server_id, user_id)
    if not db_server_user:
        return None

    updated = server_user.dict(exclude_unset=True)
    for key, val in updated.items():
        setattr(db_server_user, key, val)
    # TODO: config might be overwritten

    db.add(db_server_user)
    db.commit()
    db.refresh(db_server_user)
    return db_server_user


def delete_server_user(
    db: Session, server_id: int, user_id: int
) -> ServerUser:
    db_server_user = (
        db.query(ServerUser)
        .filter(
            and_(
                ServerUser.server_id == server_id, 
                ServerUser.user_id == user_id
            )
        )
        .first()
    )
    if not db_server_user:
        raise HTTPException(status_code=404, detail="Server user not found")
    for port in db_server_user.server.ports:
        for port_user in port.allowed_users:
            if port_user.user_id == user_id:
                db.delete(port_user)
    db.delete(db_server_user)
    db.commit()
    return db_server_user
