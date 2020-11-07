import typing as t
from pydantic import BaseModel

from app.db.schemas.user import UserOut


class PortBase(BaseModel):
    external_num: int = None
    internal_num: int
    server_id: int


class PortOut(PortBase):
    id: int

    class Config:
        orm_mode = True


class PortOpsOut(PortBase):
    id: int
    is_active: bool

    class Config:
        orm_mode = True


class PortCreate(BaseModel):
    external_num: t.Optional[int] = None
    internal_num: int
    is_active: t.Optional[bool] = True

    class Config:
        orm_mode = True


class PortEdit(BaseModel):
    external_num: t.Optional[int]
    internal_num: t.Optional[int]
    server_id: t.Optional[int]
    is_active: t.Optional[bool]

    class Config:
        orm_mode = True


class Port(PortBase):
    id: int

    class Config:
        orm_mode = True


class PortUserBase(BaseModel):
    user_id: int


class PortUserOut(PortUserBase):
    port_id: int

    class Config:
        orm_mode = True


class PortUserEdit(PortUserBase):
    class Config:
        orm_mode = True


