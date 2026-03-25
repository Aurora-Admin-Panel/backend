from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import APIRouter, Depends, HTTPException, status

from app.db.models.user import User
from app.db.schemas.auth import TokenOut
from app.db.session import get_db
from app.core import security
from app.core.auth import authenticate_user, get_current_active_user, sign_up_new_user

auth_router = r = APIRouter()

def create_token(user: User):
    access_token_expires = timedelta(
        days=security.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    if user.is_superuser:
        permissions = "admin"
    elif user.is_ops:
        permissions = "ops"
    else:
        permissions = "user"
    return security.create_access_token(
        data={"sub": user.email, "permissions": permissions},
        expires_delta=access_token_expires,
    )

@r.post("/token", response_model=TokenOut)
async def login(
    db=Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenOut(access_token=create_token(user))

@r.post("/signup", response_model=TokenOut)
async def signup(
    db=Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
    user = sign_up_new_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenOut(access_token=create_token(user))

@r.get("/token", response_model=TokenOut)
async def get_token(current_user=Depends(get_current_active_user)):
    return TokenOut(access_token=create_token(current_user))
