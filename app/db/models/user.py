from sqlalchemy.orm import relationship
from sqlalchemy import Boolean, Column, Integer, String, Text

from .base import Base


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
    notes = Column(Text, nullable=True)

    allowed_servers = relationship(
        "ServerUser", cascade="all,delete", back_populates="user"
    )
    allowed_ports = relationship(
        "PortUser", cascade="all,delete", back_populates="user"
    )
    servers = relationship(
        "Server", secondary="server_user", back_populates="users"
    )
    ports = relationship("Port", secondary="port_user", back_populates="users")

    def is_admin(self) -> bool:
        return self.is_ops or self.is_superuser
