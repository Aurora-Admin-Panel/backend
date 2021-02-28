import typing as t
from fastapi import HTTPException, status
from fastapi import APIRouter, Request, Depends, Response
from fastapi.encoders import jsonable_encoder
from fastapi_pagination import pagination_params, Page
from fastapi_pagination.paginator import paginate

from app.core.security import verify_password
from app.db.session import get_db
from app.db.crud.user import (
    get_users,
    get_user,
    create_user,
    delete_user,
    edit_user,
    edit_me,
    get_user_servers,
    get_user_ports,
)
from app.db.crud.port_forward import (
    get_forward_rule_for_user,
    delete_forward_rule_by_id,
)
from app.db.schemas.user import (
    UserCreate,
    UserEdit,
    UserDelete,
    User,
    UserOut,
    UserOpsOut,
    MeEdit,
    UserServerOut,
)
from app.core.auth import get_current_active_user, get_current_active_admin
from app.utils.size import get_readable_size
from app.utils.tasks import trigger_port_clean

users_v2_router = r = APIRouter()


@r.get(
    "/users",
    response_model=Page[UserOut],
    response_model_exclude_none=True,
    dependencies=[Depends(pagination_params)],
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
