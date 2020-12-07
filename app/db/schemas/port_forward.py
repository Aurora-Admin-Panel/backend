import typing as t
from pydantic import BaseModel

from app.db.models.port_forward import MethodEnum, TypeEnum

class IptablesConfig(BaseModel):
    type: t.Optional[TypeEnum]
    remote_ip: t.Optional[str]
    remote_address: str
    remote_port: int

class GostConfig(BaseModel):
    Retries: t.Optional[int]
    ServeNodes: t.List
    ChainNodes: t.Optional[t.List]

class V2rayConfig(BaseModel):
    inbounds: t.List
    outbounds: t.Optional[t.List]
    routing: t.Optional[t.Dict]
    dns: t.Optional[t.Dict]

class PortForwardRuleBase(BaseModel):
    config: t.Dict
    method: MethodEnum


class PortForwardRuleOut(PortForwardRuleBase):
    id: int
    status: str = None

    class Config:
        orm_mode = True


class PortForwardRuleCreate(PortForwardRuleBase):
    config: t.Union[IptablesConfig, GostConfig, V2rayConfig]

    class Config:
        orm_mode = True


class PortForwardRuleEdit(BaseModel):
    config: t.Union[IptablesConfig, GostConfig, V2rayConfig]
    method: t.Optional[MethodEnum]

    class Config:
        orm_mode = True
