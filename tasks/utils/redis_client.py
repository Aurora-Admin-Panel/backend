import redis
from app.core import config


def get_redis():
    return redis.StrictRedis(
        host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True
    )
