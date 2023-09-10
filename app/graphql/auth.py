import typing
from strawberry.permission import BasePermission
from strawberry.types import Info


class IsAuthenticated(BasePermission):
    message = "User is not authenticated"

    def has_permission(self, source: typing.Any, info: Info, **kwargs) -> bool:
        return (
            info.context["request"].state.user is not None
            and info.context["request"].state.user.is_active
        )


class IsAdmin(BasePermission):
    message = "User is not an admin"

    def has_permission(self, source: typing.Any, info: Info, **kwargs) -> bool:
        return (
            info.context["request"].state.user is not None
            and info.context["request"].state.user.is_active
            and info.context["request"].state.user.is_ops
        )


class IsSuperUser(BasePermission):
    message = "User is not a superuser"

    def has_permission(self, source: typing.Any, info: Info, **kwargs) -> bool:
        return (
            info.context["request"].state.user is not None
            and info.context["request"].state.user.is_active
            and info.context["request"].state.user.is_superuser
        )
