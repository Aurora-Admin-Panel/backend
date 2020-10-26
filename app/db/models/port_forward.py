import enum
from sqlalchemy.orm import relationship
from sqlalchemy import Boolean, Enum, Column, Integer, String, ForeignKey, UniqueConstraint

from .base import Base


class TypeEnum(enum.Enum):
    TCP = "TCP"
    UDP = "UDP"
    ALL = "ALL"


class MethodEnum(enum.Enum):
    IPTABLES = "iptables"


class PortForwardRule(Base):
    __tablename__ = "port_forward_rule"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    port_id = Column(Integer, ForeignKey('port.id'))
    type = Column(Enum(TypeEnum), nullable=False)
    method = Column(Enum(MethodEnum), nullable=False)
    remote_address = Column(String, nullable=False)
    remote_ip = Column(String, nullable=True)
    remote_port = Column(Integer, nullable=False)
    status = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    port = relationship("Port", back_populates="port_forward_rules")