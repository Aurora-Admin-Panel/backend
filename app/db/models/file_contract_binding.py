import enum
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


class FileContractBinding(Base):
    __tablename__ = "file_contract_binding"
    __table_args__ = (
        UniqueConstraint(
            "file_id",
            "contract_id",
            name="_file_contract_binding_file_id_contract_id_uc",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("file.id"), nullable=False)
    contract_id = Column(Integer, ForeignKey("executable_contract.id"), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        TIMESTAMP(timezone=True), default=datetime.now(UTC), nullable=False
    )

    file = relationship("File", back_populates="contract_bindings")
    contract = relationship("ExecutableContract", back_populates="file_bindings")
    deployments = relationship(
        "ServerDeployment",
        cascade="all,delete",
        back_populates="binding",
    )
