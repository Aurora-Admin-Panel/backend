import typing as t
from pydantic import BaseModel, validator

from app.api.utils.size import get_readable_size
from app.db.constants import LimitActionEnum

class UserOut(BaseModel):
    id: int
    email: str
    is_active: bool = True

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
    ansible_architecture: t.Optional[str]
    ansible_distribution: t.Optional[str]
    ansible_distribution_release: t.Optional[str]
    ansible_distribution_version: t.Optional[str]


class ServerConfig(BaseModel):
    facts: t.Optional[ServerFacts]

class ServerBase(BaseModel):
    name: str
    address: str


class ServerOut(ServerBase):
    id: int
    config: ServerConfig

    class Config:
        orm_mode = True


class ServerOpsOut(ServerOut):
    id: int
    ansible_name: str
    ansible_host: t.Optional[str]
    ansible_port: t.Optional[int]
    ansible_user: t.Optional[str]
    config: ServerConfig
    ssh_password: t.Optional[str]
    sudo_password: t.Optional[str]
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

    class Config:
        orm_mode = True


class Server(ServerBase):
    id: int

    class Config:
        orm_mode = True
