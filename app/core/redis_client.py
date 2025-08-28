import asyncio
from contextlib import asynccontextmanager
from redis.asyncio import Redis, ConnectionPool

from .config import REDIS_HOST, REDIS_PORT

_pool: ConnectionPool | None = None
_pubsub_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True
        )
    return _pool


def get_pubsub_pool() -> ConnectionPool:
    """Use a dedicated pool so pub/sub doesn't starve normal commands."""
    global _pubsub_pool
    if _pubsub_pool is None:
        _pubsub_pool = ConnectionPool.from_url(
            f"redis://{REDIS_HOST}:{REDIS_PORT}",
            decode_responses=True,
            max_connections=10,
        )
    return _pubsub_pool


def new_redis() -> Redis:
    return Redis(connection_pool=get_pool())


def new_pubsub_redis() -> Redis:
    return Redis(connection_pool=get_pubsub_pool())


async def ping_or_raise():
    async with Redis(connection_pool=get_pool()) as r:
        pong = await r.ping()
        if pong is not True:
            raise RuntimeError("Redis ping failed")
