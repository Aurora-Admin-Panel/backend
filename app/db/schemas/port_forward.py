import typing as t
from pydantic import BaseModel

from app.db.models.port_forward import TypeEnum, MethodEnum


class PortForwardRuleBase(BaseModel):
    type: TypeEnum
    method: MethodEnum
    remote_address: str
    remote_port: int


class PortForwardRuleOut(PortForwardRuleBase):
    id: int
    remote_ip: str
    status: str = None

    class Config:
        orm_mode = True


class PortForwardRuleCreate(PortForwardRuleBase):
    remote_ip: t.Optional[str] = None

    class Config:
        orm_mode = True


class PortForwardRuleEdit(BaseModel):
    type: t.Optional[TypeEnum]
    method: t.Optional[MethodEnum]
    remote_address: t.Optional[str]
    remote_ip: t.Optional[str]
    remote_port: t.Optional[int]

    class Config:
        orm_mode = True
