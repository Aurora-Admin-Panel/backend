import enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy import (
    Boolean,
    Enum,
    Column,
    Integer,
    String,
    JSON,
    ForeignKey,
)

from .base import Base


class TypeEnum(str, enum.Enum):
    TCP = "TCP"
    UDP = "UDP"
    ALL = "ALL"


class MethodEnum(enum.Enum):
    BROOK = "brook"
    CADDY = "caddy"
    EHCO = "ehco"
    GOST = "gost"
    IPERF = "iperf"
    IPTABLES = "iptables"
    NODE_EXPORTER = "node_exporter"
    SHADOWSOCKS = "shadowsocks"
    SOCAT = "socat"
    TINY_PORT_MAPPER = "tiny_port_mapper"
    V2RAY = "v2ray"
    WSTUNNEL = "wstunnel"
    REALM = "realm"


class PortForwardRule(Base):
    __tablename__ = "port_forward_rule"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    port_id = Column(Integer, ForeignKey("port.id"), nullable=False)
    config = Column(
        MutableDict.as_mutable(JSON), nullable=False, default=lambda: {}
    )
    method = Column(Enum(MethodEnum), nullable=False)
    status = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    port = relationship("Port", back_populates="forward_rule")
