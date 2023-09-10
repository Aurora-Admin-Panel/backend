import typing as t
from pydantic import BaseModel, validator
from .port_usage import PortUsageOut
from app.utils.size import get_readable_size


class UserBase(BaseModel):
    email: str
    is_active: bool = True
    is_ops: bool = False
    is_superuser: bool = False
    first_name: str = None
    last_name: str = None


class UserPort(BaseModel):
    port_id: int

    class Config:
        orm_mode = True


class UserServer(BaseModel):
    server_id: t.Optional[int]

    class Config:
        orm_mode = True


class UserOut(UserBase):
    id: int
    notes: t.Optional[str] = None
    allowed_ports: t.List[UserPort]
    allowed_servers: t.List[UserServer]

    class Config:
        orm_mode = True


class UserOpsOut(UserBase):
    id: int
    notes: t.Optional[str] = None
    download_usage: t.Optional[int]
    readable_download_usage: t.Optional[str]
    upload_usage: t.Optional[int]
    readable_upload_usage: t.Optional[str]
    allowed_ports: t.List[UserPort]
    allowed_servers: t.List[UserServer]

    class Config:
        orm_mode = True


class UserCreate(UserBase):
    password: str
    notes: t.Optional[str]


class UserEdit(BaseModel):
    email: t.Optional[str]
    is_active: t.Optional[bool]
    is_ops: t.Optional[bool]
    is_superuser: t.Optional[bool]
    first_name: t.Optional[str]
    last_name: t.Optional[str]
    notes: t.Optional[str]
    password: t.Optional[str] = None
    clear_rules: t.Optional[bool] = None


class UserDelete(BaseModel):
    remove_rule: t.Optional[bool] = False


class MeEdit(BaseModel):
    email: t.Optional[str]
    first_name: t.Optional[str]
    last_name: t.Optional[str]
    prev_password: t.Optional[str] = None
    new_password: t.Optional[str] = None


class User(UserBase):
    id: int

    class Config:
        orm_mode = True

    def is_admin(self) -> bool:
        return self.is_ops or self.is_superuser


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: str = None
    permissions: str = "user"


class PortUserConfig(BaseModel):
    quota: t.Optional[int]


class UserPortPortOut(BaseModel):
    id: int
    num: int
    external_num: t.Optional[int]

    class Config:
        orm_mode = True


class UserPortOut(BaseModel):
    port_id: int
    usage: t.Optional[PortUsageOut]
    config: PortUserConfig
    port: UserPortPortOut

    class Config:
        orm_mode = True


class ServerUserConfig(BaseModel):
    quota: t.Optional[int]


class UserServerServerOut(BaseModel):
    id: int
    name: str
    address: str


class UserServerOut(BaseModel):
    server_id: int
    server: UserServerServerOut
    ports: t.List[UserPortOut]
    config: ServerUserConfig
    download: t.Optional[int]
    upload: t.Optional[int]
    readable_download: t.Optional[str]
    readable_upload: t.Optional[str]

    class Config:
        orm_mode = True

    @validator("readable_download", pre=True, always=True)
    def default_readable_download(cls, v, *, values, **kwargs):
        return v or get_readable_size(values["download"])

    @validator("readable_upload", pre=True, always=True)
    def default_readable_upload(cls, v, *, values, **kwargs):
        return v or get_readable_size(values["upload"])
