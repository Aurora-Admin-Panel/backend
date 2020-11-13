from .base import Base
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy import Boolean, Column, Integer, String, JSON, ForeignKey, UniqueConstraint


class Server(Base):
    __tablename__ = "server"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    address = Column(String, nullable=False)
    ansible_name = Column(String, nullable=False)
    ansible_host = Column(String, nullable=True)
    ansible_port = Column(Integer, nullable=True, default=lambda: 22)
    ansible_user = Column(String, nullable=True, default=lambda: 'root')
    config = Column(MutableDict.as_mutable(JSON), nullable=False, default=lambda: {})
    is_active = Column(Boolean, default=True)

    ports = relationship("Port", back_populates="server")
    allowed_users = relationship("ServerUser", back_populates="server")


class ServerUser(Base):
    __tablename__ = "server_user"
    __table_args__ = UniqueConstraint('server_id', 'user_id', name='_server_user_server_id_user_id_uc'),

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("server.id"))
    user_id = Column(Integer, ForeignKey("user.id"))
    config = Column(MutableDict.as_mutable(JSON), nullable=False, default=lambda: {})

    user = relationship("User", back_populates="allowed_servers")
    server = relationship("Server", back_populates="allowed_users")


