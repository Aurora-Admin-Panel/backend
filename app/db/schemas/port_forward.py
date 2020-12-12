import typing as t
from pydantic import BaseModel

from app.db.models.port_forward import MethodEnum, TypeEnum


class IptablesConfig(BaseModel):
    type: TypeEnum
    remote_ip: t.Optional[str]
    remote_address: str
    remote_port: int


class SocatConfig(BaseModel):
    type: TypeEnum
    remote_address: str
    remote_port: int


class EhcoConfig(BaseModel):
    listen_type: str
    transport_type: str
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


class BrookConfig(BaseModel):
    command: str
    remote_address: t.Optional[str]
    remote_port: t.Optional[int]
    password: t.Optional[str]


class WsTunnelConfig(BaseModel):
    forward_type: TypeEnum
    protocol: str
    client_type: str
    proxy_port: int
    remote_address: t.Optional[str]
    remote_port: t.Optional[int]


class PortForwardRuleBase(BaseModel):
    config: t.Dict
    method: MethodEnum


class PortForwardRuleOut(PortForwardRuleBase):
    id: int
    status: str = None

    class Config:
        orm_mode = True


class PortForwardRuleCreate(PortForwardRuleBase):
    config: t.Union[
        WsTunnelConfig,
        EhcoConfig,
        BrookConfig,
        IptablesConfig,
        SocatConfig,
        GostConfig,
        V2rayConfig,
        t.Dict,
    ]

    class Config:
        orm_mode = True


class PortForwardRuleEdit(BaseModel):
    config: t.Union[
        WsTunnelConfig,
        EhcoConfig,
        BrookConfig,
        IptablesConfig,
        SocatConfig,
        GostConfig,
        V2rayConfig,
        t.Dict,
    ]
    method: t.Optional[MethodEnum]

    class Config:
        orm_mode = True
