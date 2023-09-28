import jwt
from typing import Any
from strawberry.permission import BasePermission
from strawberry.types import Info
from fastapi.security.utils import get_authorization_scheme_param
from app.core import config, security
from app.db.crud.user import get_user_by_email
from app.db.session import db_session


class EnsureUser(BasePermission):
    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        request = info.context["request"]

        if not hasattr(request.state, "user"):
            print(request.state)
            authorization = None
            if request.scope["type"] == "websocket":
                authorization = info.context["connection_params"].get(
                    "Authorization"
                )
            elif request.scope["type"] == "http":
                authorization = request.headers.get("Authorization")

            request.state.user = None
            if authorization is not None:
                scheme, token = get_authorization_scheme_param(authorization)
                if authorization and scheme.lower() == "bearer":
                    payload = jwt.decode(
                        token,
                        config.SECRET_KEY,
                        algorithms=[security.ALGORITHM],
                    )
                    email: str = payload.get("sub")
                    if email is not None:
                        with db_session() as db:
                            request.state.user = get_user_by_email(db, email)
        return request.state.user is not None


class IsAuthenticated(EnsureUser):
    message = "User is not authenticated"

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        return (
            super().has_permission(source, info, **kwargs)
            and info.context["request"].state.user.is_active
        )


class IsAdmin(EnsureUser):
    message = "User is not an admin"

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        return (
            super().has_permission(source, info, **kwargs)
            and info.context["request"].state.user.is_active
            and info.context["request"].state.user.is_ops
        )


class IsSuperUser(EnsureUser):
    message = "User is not a superuser"

    def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        return (
            super().has_permission(source, info, **kwargs)
            and info.context["request"].state.user.is_active
            and info.context["request"].state.user.is_superuser
        )
