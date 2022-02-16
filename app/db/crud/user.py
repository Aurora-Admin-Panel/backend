import typing as t
from fastapi import HTTPException, status
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from sqlalchemy import and_, or_

from app.core.security import get_password_hash
from app.db.models.port import Port, PortUser
from app.db.models.server import Server, ServerUser
from app.db.models.user import User
from app.db.schemas.user import (
    UserCreate,
    UserEdit,
    MeEdit,
)


def get_user(db: Session, user_id: int) -> User:
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .options(joinedload(User.allowed_servers))
        .options(joinedload(User.allowed_ports))
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_user_by_email(db: Session, email: str) -> User:
    return db.query(User).filter(User.email == email).first()


def get_users(db: Session, query: str = None, user: User = None):
    q = db.query(User).filter(User.is_superuser == False)
    if user and user.is_ops:
        q = db.query(User).filter(User.is_ops == False)
    if query is not None:
        q = q.filter(
            or_(
                func.lower(User.email).like(f"%{query}%"),
                func.lower(User.notes).like(f"%{query}%"),
            )
        )
    return (
        q.options(joinedload(User.allowed_servers))
        .options(joinedload(User.allowed_ports))
        .order_by(User.is_active.desc(), User.notes.asc(), User.email.asc())
        .all()
    )


def get_users_with_ports_usage(
    db: Session, query: str = None, user: User = None
):
    q = db.query(User).filter(User.is_superuser == False)
    if user and user.is_ops:
        q = db.query(User).filter(User.is_ops == False)
    if query is not None:
        q = q.filter(
            or_(
                func.lower(User.email).like(f"%{query}%"),
                func.lower(User.notes).like(f"%{query}%"),
            )
        )
    return (
        q.options(joinedload(User.allowed_servers))
        .options(
            joinedload(User.allowed_ports)
            .joinedload(PortUser.port)
            .joinedload(Port.usage)
        )
        .order_by(User.is_active.desc(), User.notes.asc(), User.email.asc())
        .all()
    )


def create_user(db: Session, user: UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = User(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        is_active=user.is_active,
        is_ops=user.is_ops,
        is_superuser=user.is_superuser,
        hashed_password=hashed_password,
    )
    if user.notes:
        setattr(db_user, "notes", user.notes)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return get_user(db, db_user.id)


def delete_user(db: Session, user: User) -> User:
    db.delete(user)
    db.commit()
    return user


def edit_user(db: Session, user_id: int, user: UserEdit) -> User:
    db_user = get_user(db, user_id)
    if not db_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    update_data = user.dict(exclude_unset=True)

    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(user.password)
        del update_data["password"]

    for key, value in update_data.items():
        setattr(db_user, key, value)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return get_user(db, db_user.id)


def edit_me(db: Session, db_user: User, user: MeEdit) -> User:
    update_data = user.dict(exclude_unset=True)

    if "new_password" in update_data:
        update_data["hashed_password"] = get_password_hash(user.new_password)
        del update_data["new_password"]

    for key, value in update_data.items():
        setattr(db_user, key, value)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user_servers(db: Session, user_id: int) -> t.List[ServerUser]:
    return (
        db.query(ServerUser)
        .filter(and_(ServerUser.user_id == user_id))
        .options(joinedload(ServerUser.server))
        .all()
    )


def get_user_ports(db: Session, user_id: int) -> t.List[PortUser]:
    return (
        db.query(PortUser)
        .filter(PortUser.user_id == user_id)
        .options(joinedload(PortUser.port))
        .all()
    )


def get_user_ports_with_usage(db: Session, user_id: int) -> t.List[PortUser]:
    return (
        db.query(PortUser)
        .filter(PortUser.user_id == user_id)
        .options(joinedload(PortUser.port).joinedload(Port.usage))
        .all()
    )
