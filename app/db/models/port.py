from .base import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, UniqueConstraint

from app.db.models.port_forward import PortForwardRule


class Port(Base):
    __tablename__ = "port"
    __table_args__ = UniqueConstraint('num', 'server_id', name='_port_num_server_uc'),

    id = Column(Integer, primary_key=True, index=True)
    num = Column(Integer, nullable=False)
    internal_num = Column(Integer)
    server_id = Column(Integer, ForeignKey('server.id'))
    is_active = Column(Boolean, default=True)

    server = relationship("Server", back_populates="ports")
    allowed_users = relationship("PortUser", back_populates="port")
    port_forward_rules = relationship("PortForwardRule", back_populates="port")


class PortUser(Base):
    __tablename__ = "port_user"
    __table_args__ = UniqueConstraint('port_id', 'user_id', name='_server_user_server_id_user_id_uc'),

    id = Column(Integer, primary_key=True, index=True)
    port_id = Column(Integer, ForeignKey("port.id"))
    user_id = Column(Integer, ForeignKey("user.id"))

    user = relationship("User", back_populates="allowed_ports")
    port = relationship("Port", back_populates="allowed_users")
