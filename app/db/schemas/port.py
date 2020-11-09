import typing as t
from pydantic import BaseModel

from app.db.schemas.user import UserOut
from app.db.schemas.port_forward import PortForwardRuleOut


class PortUserBase(BaseModel):
    user_id: int


class PortUserOut(PortUserBase):
    port_id: int

    class Config:
        orm_mode = True


class PortUserOpsOut(PortUserBase):
    port_id: int
    user: UserOut

    class Config:
        orm_mode = True


class PortUserEdit(PortUserBase):
    class Config:
        orm_mode = True


class PortBase(BaseModel):
    external_num: int = None
    num: int
    server_id: int


class PortOut(PortBase):
    id: int
    forward_rule: t.Optional[PortForwardRuleOut]


    class Config:
        orm_mode = True


class PortOpsOut(PortBase):
    id: int
    is_active: bool
    forward_rule: t.Optional[PortForwardRuleOut]
    allowed_users: t.List[PortUserOpsOut]

    class Config:
        orm_mode = True


class PortCreate(BaseModel):
    external_num: t.Optional[int] = None
    num: int
    is_active: t.Optional[bool] = True

    class Config:
        orm_mode = True


class PortEdit(BaseModel):
    external_num: t.Optional[int]
    num: t.Optional[int]
    server_id: t.Optional[int]
    is_active: t.Optional[bool]

    class Config:
        orm_mode = True

