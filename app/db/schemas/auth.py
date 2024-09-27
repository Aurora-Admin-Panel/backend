import typing as t
from pydantic import BaseModel


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
