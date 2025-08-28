from datetime import datetime, timedelta, timezone

import redis
from huey import crontab
from loguru import logger

from .config import huey
from app.core import config
from app.core.redis_keyspace import Keys


@huey.periodic_task(crontab(minute="0"))
def clean_pubsub_history():
    """
    Streams auto-expire via TTL; this just prunes the index ZSET.
    """
    r = redis.StrictRedis(config.REDIS_HOST, config.REDIS_PORT)
    ids = r.zrange(Keys.task_ids(), 0, -1)
    if not ids:
        logger.info("PubSub cleanup: nothing to prune.")
        return

    pipe = r.pipeline(transaction=False)
    for tid in ids:
        pipe.exists(Keys.task_stream(tid))
    exists_flags = pipe.execute()

    stale = [tid for tid, ex in zip(ids, exists_flags) if not ex]
    removed = 0
    if stale:
        removed = r.zrem(Keys.task_ids(), *stale)

    logger.info("PubSub cleanup: pruned %d orphan task ids.", removed)
