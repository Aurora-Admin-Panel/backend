from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Float,
    Boolean,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from .base import Base


class ServerMetric(Base):
    __tablename__ = "server_metric"

    time = Column(
        TIMESTAMP(timezone=True), nullable=False, primary_key=True, index=True
    )
    server_id = Column(
        Integer,
        ForeignKey("server.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
        index=True,
    )

    is_online = Column(Boolean, nullable=False)

    cpu_util_pct = Column(Float, nullable=False)  # was cpu_pct
    load_1m = Column(Float, nullable=False)  # was load1
    load_5m = Column(Float, nullable=False)  # was load5
    load_15m = Column(Float, nullable=False)  # was load15

    mem_used_bytes = Column(BigInteger, nullable=False)  # was mem_used
    swap_used_bytes = Column(BigInteger, nullable=False)  # was swap_used
    fs_root_used_bytes = Column(BigInteger, nullable=False)  # was root_used

    # optional deriveds
    mem_used_pct = Column(Float, nullable=True)
    fs_root_used_pct = Column(Float, nullable=True)

    server = relationship("Server", lazy="joined")


class DiskUsage(Base):
    __tablename__ = "disk_usage"

    time = Column(
        TIMESTAMP(timezone=True), nullable=False, primary_key=True, index=True
    )
    server_id = Column(
        Integer,
        ForeignKey("server.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
        index=True,
    )
    mount = Column(String, nullable=False, index=True)
    used_bytes = Column(BigInteger, nullable=False)

    server = relationship("Server", lazy="joined")


class NetworkCounter(Base):
    __tablename__ = "network_counter"

    time = Column(
        TIMESTAMP(timezone=True), nullable=False, primary_key=True, index=True
    )
    server_id = Column(
        Integer,
        ForeignKey("server.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
        index=True,
    )
    iface = Column(String, nullable=False, primary_key=True, index=True)

    rx_bytes_total = Column(BigInteger, nullable=False)
    tx_bytes_total = Column(BigInteger, nullable=False)

    server = relationship("Server", lazy="joined")
