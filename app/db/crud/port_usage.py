import typing as t
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from app.db.schemas.port_usage import (
    PortUsageBase,
    PortUsageCreate,
    PortUsageEdit,
    PortUsageOut
)
from app.db.models.port import PortUsage


def get_port_usage(db: Session, port_id: int) -> PortUsage:
    return db.query(PortUsage).filter(PortUsage.port_id == port_id).first()


def create_port_usage(db: Session, port_id: int, port_usage: PortUsageCreate) -> PortUsage:
    db_port_usage = PortUsage(**port_usage.dict(exclude_unset=True))
    db.add(db_port_usage)
    db.commit()
    db.refresh(db_port_usage)
    return db_port_usage


def edit_port_usage(
    db: Session, port_id: int, port_usage: PortUsageEdit
) -> PortUsage:
    db_port_usage = get_port_usage(db, port_id)
    if not db_port_usage:
        return None
    updated = port_usage.dict(exclude_unset=True)

    for key, val in updated.items():
        setattr(db_port_usage, key, val)

    db.add(db_port_usage)
    db.commit()
    db.refresh(db_port_usage)
    return db_port_usage


def delete_port_usage(db: Session, port_id: int) -> PortUsage:
    db_port_usage = get_port_usage(db, port_id)
    if not db_port_usage:
        return None
    db.delete(db_port_usage)
    db.commit()
    return db_port_usage
