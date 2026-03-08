from datetime import datetime, UTC

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, JSON, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from .base import Base


class ExecutableContract(Base):
    __tablename__ = "executable_contract"
    __table_args__ = (
        UniqueConstraint(
            "contract_key",
            "version",
            name="_executable_contract_contract_key_version_uc",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    contract_key = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False, default=lambda: 1)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    schema_json = Column(MutableDict.as_mutable(JSON), nullable=False, default=lambda: {})
    is_builtin = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        TIMESTAMP(timezone=True), default=datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        default=datetime.now(UTC),
        nullable=False,
        onupdate=datetime.now(UTC),
    )

    file_bindings = relationship(
        "FileContractBinding",
        cascade="all,delete",
        back_populates="contract",
    )
    deployments = relationship(
        "ServerDeployment",
        back_populates="contract",
    )

