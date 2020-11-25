import typing as t
from fastapi import HTTPException, status
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_password_hash
from app.db.models.port import Port, PortUser
from app.db.models.server import Server, ServerUser
from app.db.models.user import User
from app.db.schemas.user import (
    UserBase,
    UserCreate,
    UserEdit,
    UserOut,
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


def get_users(db: Session, skip: int = 0, limit: int = 100) -> t.List[UserOut]:
    return (
        db.query(User)
        .filter(and_(User.is_superuser == False, User.is_ops == False))
        .options(
            joinedload(User.allowed_ports)
            .joinedload(PortUser.port)
            .joinedload(Port.usage)
        )
        .options(joinedload(User.allowed_servers))
        .offset(skip)
        .limit(limit)
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
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return get_user(db, db_user.id)


def delete_user(db: Session, user_id: int):
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
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
        db.query(ServerUser).filter(and_(ServerUser.user_id == user_id)).all()
    )


def get_user_ports(db: Session, user_id: int) -> t.List[PortUser]:
    return db.query(PortUser).filter(PortUser.user_id == user_id).all()
