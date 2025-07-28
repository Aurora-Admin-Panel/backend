from huey import PriorityRedisHuey, PriorityRedisExpireHuey

from app.core import config

huey = PriorityRedisExpireHuey(
    "aurora",
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    expire_time=config.TASK_RESULTS_STORAGE_SECONDS,
)
