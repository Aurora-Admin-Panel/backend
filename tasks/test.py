import time
import redis
from app.core import config
from .config import huey


@huey.task()
def test_task():
    r = redis.Redis(host='redis', port=6379, db=0)
    count = 0
    while True:
        if count % 100 != 0:
            r.publish(config.PUBSUB_PREFIX+'test', str(count))
        else:
            r.publish(config.PUBSUB_PREFIX+'test', config.PUBSUB_STOPWORDS)
        count += 1
        print(count)
        time.sleep(1)
