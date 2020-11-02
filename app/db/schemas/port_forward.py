import typing as t
from pydantic import BaseModel

from app.db.models.port_forward import MethodEnum


class PortForwardRuleBase(BaseModel):
    config: t.Dict
    method: MethodEnum


class PortForwardRuleOut(PortForwardRuleBase):
    id: int
    status: str = None

    class Config:
        orm_mode = True


class PortForwardRuleCreate(PortForwardRuleBase):

    class Config:
        orm_mode = True


class PortForwardRuleEdit(BaseModel):
    config: t.Optional[t.Dict]
    method: t.Optional[MethodEnum]

    class Config:
        orm_mode = True
