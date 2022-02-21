import time
import typing as t

from pydantic import BaseModel, validator

from app.db.models.port_forward import MethodEnum, TypeEnum
from app.utils.ip import is_ip, is_ipv6


def check_type(forward_type: str) -> str:
    if forward_type not in ("TCP", "UDP", "ALL"):
        raise ValueError(f"Invalid forward type: {forward_type}")
    return forward_type


def check_ip(ip: str) -> str:
    if not (is_ip(ip) or is_ipv6(ip)):
        raise ValueError(f"Invalid ip: {ip}")
    return ip


def check_port(port: int) -> int:
    if port < 0 or port > 65535:
        raise ValueError(f"Invalid port: {port}")
    return port


def check_config(config: t.Dict, values: t.Dict) -> t.Dict:
    method = values.get("method")
    config = eval(method.name.capitalize() + "Config(**config)")
    return config


class IptablesConfig(BaseModel):
    type: TypeEnum
    remote_ip: t.Optional[str]
    remote_address: str
    remote_port: int

    _type = validator("type", pre=True, allow_reuse=True)(check_type)
    _remote_ip = validator("remote_ip", pre=True, allow_reuse=True)(check_ip)
    _remote_port = validator("remote_port", allow_reuse=True)(check_port)


class SocatConfig(BaseModel):
    type: TypeEnum
    remote_address: str
    remote_port: int

    _type = validator("type", pre=True, allow_reuse=True)(check_type)
    _remote_port = validator("remote_port", allow_reuse=True)(check_port)


class EhcoConfig(BaseModel):
    listen_type: str
    transport_type: str
    remote_address: str
    remote_port: int

    _remote_port = validator("remote_port", allow_reuse=True)(check_port)

    @validator("listen_type", pre=True)
    def check_listen_type(cls, v):
        if v not in ("raw", "ws", "wss", "mwss"):
            raise ValueError(f"Invalid listen type: {v}")
        return v

    @validator("transport_type", pre=True)
    def check_transport_type(cls, v):
        if v not in ("raw", "ws", "wss", "mwss"):
            raise ValueError(f"Invalid transport type: {v}")
        return v


class GostConfig(BaseModel):
    Retries: t.Optional[int]
    ServeNodes: t.List
    ChainNodes: t.Optional[t.List]


class IperfConfig(BaseModel):
    expire_second: int
    expire_time: t.Optional[int]

    @validator("expire_second", pre=True)
    def check_expire_second(cls, v):
        if v <= 0:
            raise ValueError("Expire second must be greater than 0")
        elif v > 24 * 60 * 60:
            raise ValueError(f"Expire second must be less than {24 * 60 * 60}")
        return v

    @validator("expire_time", pre=True, always=True)
    def add_expire_time(cls, v, values):
        if not v:
            v = time.time() + values["expire_second"]
        return v


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
    core: t.Optional[str]

    @validator("core", pre=True)
    def check_core(cls, v):
        if v not in ("v2ray", "xray"):
            raise ValueError(f"Invalid v2ray core: {v}")
        return v


class RealmConfig(BaseModel):
    remote_address: str
    remote_port: int

    _remote_port = validator("remote_port", allow_reuse=True)(check_port)


class BrookConfig(BaseModel):
    command: str
    remote_ip: t.Optional[str]
    remote_address: t.Optional[str]
    remote_port: t.Optional[int]
    server_address: t.Optional[str]
    server_port: t.Optional[int]
    password: t.Optional[str]

    _remote_port = validator("remote_port", allow_reuse=True)(check_port)

    @validator("command", pre=True)
    def check_command(cls, v):
        if v not in ("relay", "server", "wsserver", "client", "wsclient"):
            raise ValueError(f"Invalid command: {v}")
        return v

    @validator("password", pre=True, always=True)
    def check_password(cls, v, values):
        command = values.get("command")
        if command != "relay" and not v:
            raise ValueError("Password is necessary for tunnel model")
        return v


class WstunnelConfig(BaseModel):
    forward_type: TypeEnum
    protocol: str
    client_type: str
    proxy_port: int
    remote_address: t.Optional[str]
    remote_port: t.Optional[int]

    _proxy_port = validator("proxy_port", allow_reuse=True)(check_port)
    _remote_port = validator("remote_port", allow_reuse=True)(check_port)

    @validator("forward_type", pre=True)
    def check_forward_type(cls, v):
        if v not in ("TCP", "UDP"):
            raise ValueError(f"Invalid command: {v}")
        return v

    @validator("protocol", pre=True)
    def check_protocol(cls, v):
        if v not in ("ws", "wss"):
            raise ValueError(f"Invalid protocol: {v}")
        return v

    @validator("client_type", pre=True)
    def check_client_type(cls, v):
        if v not in ("server", "client"):
            raise ValueError(f"Invalid client type: {v}")
        return v


class ShadowsocksConfig(BaseModel):
    password: str
    encryption: str
    udp: t.Optional[bool]

    @validator("encryption", pre=True)
    def check_encryption(cls, v):
        if v not in (
            "AEAD_AES_128_GCM",
            "AEAD_AES_256_GCM",
            "AEAD_CHACHA20_POLY1305",
            "aes-128-cfb",
            "aes-192-cfb",
            "aes-256-cfb",
            "aes-128-ctr",
            "aes-192-ctr",
            "aes-256-ctr",
            "des-cfb",
            "bf-cfb",
            "cast5-cfb",
            "rc4-md5",
            "rc4-md5-6",
            "chacha20",
            "chacha20-ietf",
            "salsa20",
        ):
            raise ValueError(f"Invalid encryption: {v}")
        return v


class HaproxyConfig(BaseModel):
    mode: str
    maxconn: int
    send_proxy: str
    balance_mode: str
    backend_nodes: t.List

    @validator("mode", pre=True)
    def check_mode(cls, v):
        if v not in ("tcp", "http"):
            raise ValueError(f"Invalid mode: {v}")
        return v

    @validator("send_proxy", pre=True)
    def check_send_proxy(cls, v):
        if v and v not in ("send-proxy", "send-proxy-v2"):
            raise ValueError(f"Invalid send proxy: {v}")
        return v

    @validator("balance_mode", pre=True)
    def check_balance_mode(cls, v):
        if v not in (
            "roundrobin",
            "static-rr",
            "leastconn",
            "first",
            "source",
        ):
            raise ValueError(f"Invalid balance mode: {v}")
        return v


class PortForwardRuleBase(BaseModel):
    method: MethodEnum
    config: t.Dict


class PortForwardRuleOut(PortForwardRuleBase):
    id: int
    status: str = None

    class Config:
        orm_mode = True


class PortForwardRuleArtifacts(BaseModel):
    stdout: t.Optional[str]


class PortForwardRuleCreate(PortForwardRuleBase):
    method: MethodEnum
    config: t.Dict

    _config = validator("config", pre=True, allow_reuse=True)(check_config)

    class Config:
        orm_mode = True


class PortForwardRuleEdit(BaseModel):
    method: MethodEnum
    config: t.Dict

    _config = validator("config", pre=True, allow_reuse=True)(check_config)

    class Config:
        orm_mode = True
