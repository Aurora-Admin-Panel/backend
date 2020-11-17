import typing as t
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, relationship
from sqlalchemy import Boolean, Column, Integer, String

from .base import Base
from app.core.security import get_password_hash
from .server import ServerUser
from .port import PortUser


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_ops = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)

    allowed_servers = relationship("ServerUser", back_populates="user")
    allowed_ports = relationship("PortUser", back_populates="user")


    def is_admin(self) -> bool:
        return self.is_ops or self.is_superuser