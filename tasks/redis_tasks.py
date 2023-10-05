import redis
from datetime import datetime, timedelta

from huey import crontab
from loguru import logger

from .config import huey
from app.core import config


@huey.periodic_task(crontab(minute="*/60"))
def clean_pubsub_history():
    ts = int(
        (
            datetime.utcnow() - timedelta(days=config.TASK_OUTPUT_STORAGE_DAYS)
        ).timestamp()
        * 1000
    )
    with redis.Redis(
        host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True
    ) as r:
        count = 0
        for task_id in r.zrangebyscore("aurora:task:ids", "-inf", ts):
            count += r.delete(f"{config.PUBSUB_PREFIX}:{task_id}:history")
        logger.info(
            f"Removed {count} history items, removed "
            f"{r.zremrangebyscore('aurora:task:ids', '-inf', ts)} task ids"
        )
