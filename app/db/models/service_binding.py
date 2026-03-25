from datetime import datetime, UTC

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from .base import Base


class ServiceBinding(Base):
    __tablename__ = "service_binding"
    __table_args__ = (
        UniqueConstraint(
            "file_id",
            "service_id",
            name="_service_binding_file_id_service_id_uc",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("file.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("service_definition.id"), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        TIMESTAMP(timezone=True), default=datetime.now(UTC), nullable=False
    )

    file = relationship("File", back_populates="service_bindings")
    service = relationship("ServiceDefinition", back_populates="bindings")
    deployments = relationship(
        "ServerDeployment",
        cascade="all,delete",
        back_populates="service_binding",
    )
