import typing as t
from sqlalchemy import and_
from sqlalchemy.orm import Session
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
) -> t.Union[t.List[ServerOpsOut], t.List[ServerOut]]:
    if user.is_superuser or user.is_ops:
        servers = [
            ServerOpsOut(**server.__dict__)
            for server in db.query(Server).offset(offset).limit(limit).all()
        ]
    else:
        servers = [
            ServerOut(**server.__dict__)
            for server in db.query(Server)
            .filter(Server.allowed_users.any(user_id=user.id))
            .offset(offset)
            .limit(limit)
            .all()
        ]
    return servers


def get_server(
    db: Session, server_id: int, user: User = None
) -> Server:
    server = db.query(Server).filter(Server.id == server_id).first()
    if user:
        if not user.is_superuser and not user.is_ops:
            if not any(user.id == u.id for u in server.allowed_users):
                raise HTTPException(
                    status_code=403,
                    detail="User not allowed to access this server",
                )
    return server


def create_server(db: Session, server: ServerCreate, user: User) -> Server:
    if not user.is_ops and not user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Only superuser or ops are allowed to create servers.",
        )
    if server.ansible_host is None:
        server.ansible_host = server.address
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


def delete_server_user(
    db: Session, server_id: int, user_id: int
) -> ServerUser:
    db_server_user = (
        db.query(ServerUser)
        .filter(and_(ServerUser.server_id==server_id, ServerUser.user_id==user_id))
        .first()
    )
    if not db_server_user:
        raise HTTPException(status_code=404, detail="Server user not found")
    db.delete(db_server_user)
    db.commit()
    return db_server_user