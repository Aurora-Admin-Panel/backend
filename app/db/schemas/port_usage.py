import typing as t
from pydantic import BaseModel

from app.db.models.port_forward import MethodEnum


class PortUsageBase(BaseModel):
    port_id: int
    download: int
    upload: int


class PortUsageOut(PortUsageBase):
    id: int

    class Config:
        orm_mode = True


class PortUsageCreate(PortUsageBase):
    download: t.Optional[int] = 0
    upload: t.Optional[int] = 0
    download_accumulate: t.Optional[int] = 0
    upload_accumulate: t.Optional[int] = 0
    download_checkpoint: t.Optional[int] = 0
    upload_checkpoint: t.Optional[int] = 0


class PortUsageEdit(PortUsageBase):
    download: t.Optional[int]
    upload: t.Optional[int]
    download_accumulate: t.Optional[int]
    upload_accumulate: t.Optional[int]
    download_checkpoint: t.Optional[int]
    upload_checkpoint: t.Optional[int]