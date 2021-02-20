import typing as t
from pydantic import BaseModel, validator

from app.utils.size import get_readable_size


class PortUsageBase(BaseModel):
    port_id: int
    download: int
    upload: int


class PortUsageOut(PortUsageBase):
    readable_download: t.Optional[str]
    readable_upload: t.Optional[str]

    class Config:
        orm_mode = True

    @validator("readable_download", pre=True, always=True)
    def default_readable_download(cls, v, *, values, **kwargs):
        return v or get_readable_size(values["download"])

    @validator("readable_upload", pre=True, always=True)
    def default_readable_upload(cls, v, *, values, **kwargs):
        return v or get_readable_size(values["upload"])


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
