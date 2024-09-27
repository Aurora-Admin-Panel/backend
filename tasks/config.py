from huey import PriorityRedisHuey

from app.core import config

huey = PriorityRedisHuey("aurora", host=config.REDIS_HOST, port=config.REDIS_PORT)
