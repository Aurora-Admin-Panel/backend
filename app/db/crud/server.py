import typing as t
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.core.security import get_password_hash
from app.db.schemas.user import User
from app.db.schemas.server import (
    ServerBase,
    ServerCreate,
    ServerEdit,
    ServerOut,
    ServerOpsOut,
    ServerUserEdit,
    ServerUserOut,
)
from app.db.models.server import Server, ServerUser


def get_servers(
    db: Session, user: User, offset: int = 0, limit: int = 100
) -> t.List[Server]:
    if user.is_superuser or user.is_ops:
        return (
            db.query(Server)
            .options(joinedload(Server.allowed_users).joinedload(ServerUser.user))
            .offset(offset)
            .limit(limit)
            .all()
        )
    return (
        db.query(Server)
        .filter(Server.allowed_users.any(user_id=user.id))
        .order_by(Server.address)
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_server(db: Session, server_id: int) -> Server:
    return (
        db.query(Server)
        .filter(Server.id == server_id)
        .options(joinedload(Server.allowed_users).joinedload(ServerUser.user))
        .first()
    )


def create_server(db: Session, server: ServerCreate) -> Server:
    db_server = Server(**server.dict())
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    return db_server


def edit_server(db: Session, server_id: int, server: ServerEdit) -> Server:
    db_server = get_server(db, server_id)
    if not db_server:
        raise HTTPException(status_code=404, detail="Server not found")
    updated = server.dict(exclude_unset=True)

    for key, val in updated.items():
        setattr(db_server, key, val)

    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    return db_server


def delete_server(db: Session, server_id: int) -> Server:
    db_server = get_server(db, server_id)
    if not db_server:
        raise HTTPException(status_code=404, detail="Server not found")
    db.delete(db_server)
    db.commit()
    return db_server


def get_server_users(db: Session, server_id: int) -> t.List[ServerUser]:
    server_users = db.query(ServerUser).filter(server_id == server_id).all()
    return server_users


def add_server_user(
    db: Session, server_id: int, server_user: ServerUserEdit
) -> ServerUser:
    db_server_user = ServerUser(
        **server_user.dict(exclude_unset=True), server_id=server_id
    )
    db.add(db_server_user)
    db.commit()
    db.refresh(db_server_user)
    return db_server_user


def delete_server_user(db: Session, server_id: int, user_id: int) -> ServerUser:
    db_server_user = (
        db.query(ServerUser)
        .filter(
            and_(
                ServerUser.server_id == server_id, ServerUser.user_id == user_id
            )
        )
        .first()
    )
    if not db_server_user:
        raise HTTPException(status_code=404, detail="Server user not found")
    db.delete(db_server_user)
    db.commit()
    return db_server_user