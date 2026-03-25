import typing as t

from app.core.auth import get_current_active_admin, get_current_active_user
from app.core.security import verify_password
from app.db.crud.port_forward import (
    delete_forward_rule_by_id,
    get_forward_rule_for_user,
)
from app.db.crud.user import (
    create_user,
    delete_user,
    edit_me,
    edit_user,
    get_user,
    get_user_ports,
    get_user_servers,
    get_users,
)
from app.db.schemas.user import (
    MeEdit,
    User,
    UserCreate,
    UserDelete,
    UserEdit,
    UserOpsOut,
    UserOut,
    UserServerOut,
)
from app.db.session import get_db
from app.utils.size import get_readable_size
from app.utils.tasks import trigger_port_clean
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi_pagination import Page, add_pagination, paginate

users_v2_router = r = APIRouter()


@r.get(
    "/users",
    response_model=Page[UserOut],
    response_model_exclude_none=True,
)
async def users_list(
    response: Response,
    query: str = None,
    db=Depends(get_db),
    current_user=Depends(get_current_active_admin),
):
    """
    Search all users
    """
    return paginate(get_users(db, query=query, user=current_user))


add_pagination(users_v2_router)
