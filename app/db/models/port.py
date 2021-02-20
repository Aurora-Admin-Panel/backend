from .base import Base
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy import Boolean, Column, Integer, String, JSON, ForeignKey, UniqueConstraint, BigInteger, Text

from app.db.models.port_forward import PortForwardRule, MethodEnum


class Port(Base):
    __tablename__ = "port"
    __table_args__ = (
        UniqueConstraint('num', 'server_id', name='_port_num_server_uc'),
        UniqueConstraint('external_num', 'server_id', name='_port_external_num_server_uc'),
    )

    id = Column(Integer, primary_key=True, index=True)
    external_num = Column(Integer, nullable=True)
    num = Column(Integer, nullable=False)
    server_id = Column(Integer, ForeignKey('server.id'))
    config = Column(MutableDict.as_mutable(JSON), nullable=False, default=lambda: {})
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    server = relationship("Server", back_populates="ports")
    users = relationship("User", secondary="port_user", back_populates="ports")
    allowed_users = relationship("PortUser", cascade="all,delete", back_populates="port", lazy='joined')
    forward_rule = relationship("PortForwardRule", uselist=False, cascade="all,delete", back_populates="port", lazy='joined')
    usage = relationship("PortUsage", uselist=False, cascade="all,delete", back_populates="port", lazy='joined')


class PortUser(Base):
    __tablename__ = "port_user"
    __table_args__ = UniqueConstraint('port_id', 'user_id', name='_port_user_server_id_user_id_uc'),

    id = Column(Integer, primary_key=True, index=True)
    port_id = Column(Integer, ForeignKey("port.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    config = Column(MutableDict.as_mutable(JSON), nullable=False, default=lambda: {})

    user = relationship("User", back_populates="allowed_ports")
    port = relationship("Port", back_populates="allowed_users")


class PortUsage(Base):
    __tablename__ = "port_usage"
    __table_args__ = (
        UniqueConstraint('port_id', name='_port_usage_port_id_uc'),
    )

    id = Column(Integer, primary_key=True, index=True)
    port_id = Column(Integer, ForeignKey("port.id"), nullable=False)
    download = Column(BigInteger, nullable=False, default=lambda: 0)
    upload = Column(BigInteger, nullable=False, default=lambda: 0)
    download_accumulate = Column(BigInteger, nullable=False, default=lambda: 0)
    upload_accumulate = Column(BigInteger, nullable=False, default=lambda: 0)
    download_checkpoint = Column(BigInteger, nullable=False, default=lambda: 0)
    upload_checkpoint = Column(BigInteger, nullable=False, default=lambda: 0)

    port = relationship("Port", back_populates="usage")
