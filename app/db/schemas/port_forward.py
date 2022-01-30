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


class IperfConfig(BaseModel):
    expire_second: int


class V2rayConfig(BaseModel):
    inbound: t.Dict
    outbound: t.Dict
    custom_inbound: t.Optional[bool]
    custom_outbound: t.Optional[bool]
    tls_provider: t.Optional[str]
    tls_settings: t.Optional[t.Dict]
    reverse_proxy: t.Optional[int]
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


class ShadowsocksConfig(BaseModel):
    password: str
    encryption: str
    udp: t.Optional[bool]


class HaproxyConfig(BaseModel):
    mode: str
    maxconn: int
    send_proxy: str
    balance_mode: str
    backend_nodes: t.List


class PortForwardRuleBase(BaseModel):
    config: t.Dict
    method: MethodEnum


class PortForwardRuleOut(PortForwardRuleBase):
    id: int
    status: str = None

    class Config:
        orm_mode = True


class PortForwardRuleArtifacts(BaseModel):
    stdout: t.Optional[str]


class PortForwardRuleCreate(PortForwardRuleBase):
    config: t.Union[
        ShadowsocksConfig,
        WsTunnelConfig,
        EhcoConfig,
        BrookConfig,
        IptablesConfig,
        SocatConfig,
        GostConfig,
        V2rayConfig,
        HaproxyConfig,
        t.Dict,
    ]

    class Config:
        orm_mode = True


class PortForwardRuleEdit(BaseModel):
    config: t.Union[
        ShadowsocksConfig,
        WsTunnelConfig,
        EhcoConfig,
        BrookConfig,
        IptablesConfig,
        SocatConfig,
        IperfConfig,
        GostConfig,
        V2rayConfig,
        HaproxyConfig,
        t.Dict,
    ]
    method: t.Optional[MethodEnum]

    class Config:
        orm_mode = True
