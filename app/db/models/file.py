import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy.orm import relationship
from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    Text,
    Enum,
    BigInteger,
    DateTime,
)
from .base import Base


class FileTypeEnum(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    SECRET = "secret"
    EXECUTABLE = "executable"


class File(Base):
    __tablename__ = "file"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    type = Column(Enum(FileTypeEnum), nullable=False)
    size = Column(BigInteger, nullable=False)
    storage_path = Column(String, nullable=False)
    version = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        onupdate=datetime.utcnow,
    )

    servers = relationship("Server", back_populates="key_file")
