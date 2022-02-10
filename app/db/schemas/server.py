import typing as t
from pydantic import BaseModel, validator

from app.utils.size import get_readable_size
from app.db.constants import LimitActionEnum


class UserOut(BaseModel):
    id: int
    email: str
    is_active: bool = True
    is_ops: bool = False

    class Config:
        orm_mode = True


class ServerUserConfig(BaseModel):
    valid_until: t.Optional[int]
    due_action: t.Optional[LimitActionEnum]
    quota: t.Optional[int]
    quota_action: t.Optional[LimitActionEnum]


class ServerUserBase(BaseModel):
    server_id: int
    user_id: int


class ServerUserOut(ServerUserBase):
    config: ServerUserConfig

    class Config:
        orm_mode = True


class ServerUserOpsOut(ServerUserBase):
    user: UserOut
    config: ServerUserConfig
    download: t.Optional[int]
    upload: t.Optional[int]
    readable_download: t.Optional[str]
    readable_upload: t.Optional[str]

    class Config:
        orm_mode = True

    @validator('readable_download', pre=True, always=True)
    def default_readable_download(cls, v, *, values, **kwargs):
        return v or get_readable_size(values['download'])

    @validator('readable_upload', pre=True, always=True)
    def default_readable_upload(cls, v, *, values, **kwargs):
        return v or get_readable_size(values['upload'])


class ServerUserCreate(BaseModel):
    user_id: int

    class Config:
        orm_mode = True


class ServerUserEdit(BaseModel):
    config: t.Optional[ServerUserConfig]

    class Config:
        orm_mode = True


class ServerFacts(BaseModel):
    msg: t.Optional[str]
    os_family: t.Optional[str]
    architecture: t.Optional[str]
    distribution: t.Optional[str]
    distribution_release: t.Optional[str]
    distribution_version: t.Optional[str]


class ServerConfig(BaseModel):
    system: t.Optional[ServerFacts]
    brook: t.Optional[str]
    brook_disabled: t.Optional[bool]
    caddy: t.Optional[str]
    caddy_disabled: t.Optional[bool]
    ehco: t.Optional[str]
    ehco_disabled: t.Optional[bool]
    gost: t.Optional[str]
    gost_disabled: t.Optional[bool]
    node_exporter: t.Optional[str]
    node_exporter_disabled: t.Optional[bool]
    shadowsocks: t.Optional[str]
    shadowsocks_disabled: t.Optional[bool]
    socat: t.Optional[str]
    socat_disabled: t.Optional[bool]
    tiny_port_mapper: t.Optional[str]
    tiny_port_mapper_disabled: t.Optional[bool]
    v2ray: t.Optional[str]
    v2ray_disabled: t.Optional[bool]
    wstunnel: t.Optional[str]
    wstunnel_disabled: t.Optional[bool]
    realm: t.Optional[str]
    realm_disabled: t.Optional[bool]
    iperf: t.Optional[str]
    iperf_disabled: t.Optional[bool]
    haproxy: t.Optional[str]
    haproxy_disabled: t.Optional[bool]


class ServerBase(BaseModel):
    name: str
    address: str


class ServerPortUserOut(BaseModel):
    user_id: int

    class Config:
        orm_mode = True


class ServerPortOut(BaseModel):
    id: int
    num: int
    external_num: t.Optional[int]
    allowed_users: t.List[ServerPortUserOut]

    class Config:
        orm_mode = True


class ServerOut(ServerBase):
    id: int
    config: ServerConfig
    ports: t.List[ServerPortOut]

    class Config:
        orm_mode = True


class ServerOpsOut(ServerOut):
    id: int
    ansible_name: str
    ansible_host: t.Optional[str]
    ansible_port: t.Optional[int]
    ansible_user: t.Optional[str]
    ssh_password: t.Optional[str]
    sudo_password: t.Optional[str]
    config: ServerConfig
    allowed_users: t.List[ServerUserOpsOut]
    is_active: bool

    class Config:
        orm_mode = True

    @validator('ssh_password', pre=True, always=True)
    def default_ssh_password(cls, v):
        return 'masked' if v else None

    @validator('sudo_password', pre=True, always=True)
    def default_sudo_password(cls, v):
        return 'masked' if v else None


class ServerCreate(ServerBase):
    ansible_name: str
    ansible_host: t.Optional[str] = None
    ansible_port: t.Optional[int] = 22
    ansible_user: t.Optional[str]
    ssh_password: t.Optional[str]
    sudo_password: t.Optional[str]

    class Config:
        orm_mode = True


class ServerEdit(BaseModel):
    name: t.Optional[str]
    address: t.Optional[str]
    ansible_name: t.Optional[str]
    ansible_host: t.Optional[str]
    ansible_port: t.Optional[int]
    ansible_user: t.Optional[str]
    ssh_password: t.Optional[str]
    sudo_password: t.Optional[str]
    is_active: t.Optional[bool]
    config: t.Optional[ServerConfig]

    class Config:
        orm_mode = True


class ServerConfigEdit(BaseModel):
    brook_disabled: t.Optional[bool]
    caddy_disabled: t.Optional[bool]
    ehco_disabled: t.Optional[bool]
    gost_disabled: t.Optional[bool]
    node_exporter_disabled: t.Optional[bool]
    shadowsocks_disabled: t.Optional[bool]
    socat_disabled: t.Optional[bool]
    tiny_port_mapper_disabled: t.Optional[bool]
    v2ray_disabled: t.Optional[bool]
    wstunnel_disabled: t.Optional[bool]
    realm_disabled: t.Optional[bool]
    iperf_disabled: t.Optional[bool]
    haproxy_disabled: t.Optional[bool]

    class Config:
        orm_mode = True


class ServerConnectArg(BaseModel):
    update_gost: t.Optional[bool] = False
    update_v2ray: t.Optional[bool] = False


class Server(ServerBase):
    id: int

    class Config:
        orm_mode = True
