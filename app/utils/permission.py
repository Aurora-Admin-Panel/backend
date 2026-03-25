from sqlalchemy import select

from app.db.async_session import async_db_session
from app.db.models import User as DBUser, ServerUser, Server


async def has_permission_of_server(user: DBUser, server_id: int) -> bool:
    if user.is_superuser:
        return True
    
    async with async_db_session() as db:
        return await db.execute(
            select(ServerUser)
            .where(ServerUser.user_id == user.id)
            .joinedload(ServerUser.server)
            .where(Server.id == server_id)
        ).first()
