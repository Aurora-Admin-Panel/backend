import json
import asyncio
import async_timeout
from typing import AsyncGenerator, List, Optional, Dict

import redis.asyncio as redis
from strawberry.types import Info
from strawberry.scalars import JSON

import tasks
from app.core import config
from app.utils.permission import has_permission_of_server


async def subscribe(channel: str) -> AsyncGenerator[JSON, None]:
    conn = redis.Redis(host="redis", port=6379, db=0, decode_responses=True)
    async with conn.pubsub() as pubsub:
        await pubsub.subscribe(config.PUBSUB_PREFIX + channel)
        while True:
            try:
                # It seems the timeout only works for redis connection
                async with async_timeout.timeout(config.PUBSUB_TIMEOUT_SECONDS):
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                    )
                    if message:
                        if message["data"] == config.PUBSUB_STOPWORDS:
                            break
                        yield {
                            "type": "message",
                            "data": message["data"],
                        }
                    await asyncio.sleep(config.PUBSUB_SLEEP_SECONDS)
            except asyncio.TimeoutError:
                break


async def task(name: str, xargs: JSON) -> AsyncGenerator[JSON, None]:
    task_func = getattr(tasks, name, None)
    if not task_func:
        yield {'error': f"Task '{name}' not found"}
        return

    result = task_func(**json.loads(xargs))
    while True:
        res = result.get()
        if res is not None:
            break
        await asyncio.sleep(0.1)
    yield res
