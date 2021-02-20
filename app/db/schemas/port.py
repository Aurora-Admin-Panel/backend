import typing as t
from pydantic import BaseModel

from app.db.constants import LimitActionEnum
from app.db.schemas.port_usage import PortUsageOut
from app.db.schemas.port_forward import PortForwardRuleOut


class UserOut(BaseModel):
    id: int
    email: str
    is_active: bool = True

    class Config:
        orm_mode = True


class PortUserConfig(BaseModel):
    pass


class PortUserBase(BaseModel):
    user_id: int


class PortUserOut(PortUserBase):
    user_id: int
    port_id: int
    config: PortUserConfig

    class Config:
        orm_mode = True


class PortUserOpsOut(PortUserBase):
    user_id: int
    port_id: int
    user: UserOut
    config: PortUserConfig

    class Config:
        orm_mode = True


class PortUserCreate(PortUserBase):
    user_id: int
    config: t.Optional[PortUserConfig]

    class Config:
        orm_mode = True


class PortUserEdit(PortUserBase):
    user_id: t.Optional[int]
    config: t.Optional[PortUserConfig]

    class Config:
        orm_mode = True


class PortConfig(BaseModel):
    egress_limit: t.Optional[int]
    ingress_limit: t.Optional[int]
    valid_until: t.Optional[int]
    due_action: t.Optional[LimitActionEnum] = LimitActionEnum.NO_ACTION
    quota: t.Optional[int]
    quota_action: t.Optional[LimitActionEnum] = LimitActionEnum.NO_ACTION


class PortBase(BaseModel):
    external_num: int = None
    notes: t.Optional[str]
    num: int
    server_id: int
    config: t.Optional[PortConfig]


class PortOut(PortBase):
    id: int
    usage: t.Optional[PortUsageOut]
    forward_rule: t.Optional[PortForwardRuleOut]
    allowed_users: t.List[PortUserOpsOut]

    class Config:
        orm_mode = True


class PortOpsOut(PortBase):
    id: int
    is_active: bool
    usage: t.Optional[PortUsageOut]
    forward_rule: t.Optional[PortForwardRuleOut]
    allowed_users: t.List[PortUserOpsOut]

    class Config:
        orm_mode = True


class PortCreate(BaseModel):
    num: int
    external_num: t.Optional[int] = None
    notes: t.Optional[str]
    config: PortConfig
    is_active: t.Optional[bool] = True

    class Config:
        orm_mode = True


class PortEditBase(BaseModel):
    notes: t.Optional[str]

    class Config:
        orm_mode = True


class PortEdit(PortEditBase):
    external_num: t.Optional[int]
    is_active: t.Optional[bool]
    config: t.Optional[PortConfig]

    class Config:
        orm_mode = True
