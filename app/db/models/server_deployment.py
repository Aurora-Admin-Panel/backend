import enum
from datetime import datetime, UTC

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    Text,
    JSON,
    Enum,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from .base import Base


class DeploymentStatusEnum(str, enum.Enum):
    PENDING = "pending"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    STOPPED = "stopped"
    REMOVING = "removing"


class DeploymentActionEnum(str, enum.Enum):
    DEPLOY = "deploy"
    REDEPLOY = "redeploy"
    STOP = "stop"
    START = "start"
    REMOVE = "remove"


class DeploymentLogStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ServerDeployment(Base):
    __tablename__ = "server_deployment"

    id = Column(Integer, primary_key=True, index=True)
    binding_id = Column(
        Integer, ForeignKey("file_contract_binding.id"), nullable=True
    )
    contract_id = Column(
        Integer, ForeignKey("executable_contract.id"), nullable=True
    )
    server_id = Column(Integer, ForeignKey("server.id"), nullable=False)
    values_json = Column(MutableDict.as_mutable(JSON), nullable=False, default=lambda: {})
    status = Column(
        Enum(DeploymentStatusEnum),
        nullable=False,
        default=DeploymentStatusEnum.PENDING,
    )
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

    binding = relationship("FileContractBinding", back_populates="deployments")
    contract = relationship("ExecutableContract", back_populates="deployments")
    server = relationship("Server", back_populates="deployments")
    logs = relationship(
        "DeploymentLog",
        cascade="all,delete",
        back_populates="deployment",
        order_by="DeploymentLog.created_at.desc()",
    )


class DeploymentLog(Base):
    __tablename__ = "deployment_log"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(
        Integer, ForeignKey("server_deployment.id"), nullable=False
    )
    action = Column(Enum(DeploymentActionEnum), nullable=False)
    status = Column(
        Enum(DeploymentLogStatusEnum),
        nullable=False,
        default=DeploymentLogStatusEnum.PENDING,
    )
    plan_json = Column(JSON, nullable=True)
    output = Column(Text, nullable=True)
    task_id = Column(String, nullable=True)
    created_by_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True), default=datetime.now(UTC), nullable=False
    )
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)

    deployment = relationship("ServerDeployment", back_populates="logs")
    created_by = relationship("User")
