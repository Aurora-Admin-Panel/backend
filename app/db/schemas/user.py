from pydantic import BaseModel
import typing as t


class UserBase(BaseModel):
    email: str
    is_active: bool = True
    is_ops: bool = False
    is_superuser: bool = False
    first_name: str = None
    last_name: str = None


class UserOut(UserBase):
    pass


class UserCreate(UserBase):
    password: str

    class Config:
        orm_mode = True


class UserEdit(BaseModel):
    email: t.Optional[str]
    is_active: t.Optional[bool]
    is_ops: t.Optional[bool]
    is_superuser: t.Optional[bool]
    first_name: t.Optional[str]
    last_name: t.Optional[str]
    password: t.Optional[str] = None

    class Config:
        orm_mode = True


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
