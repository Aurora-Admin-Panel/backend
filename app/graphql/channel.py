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


async def subscribe(channel_id: str) -> AsyncGenerator[JSON, None]:
    conn = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)
    async with conn.pubsub() as pubsub:
        await pubsub.subscribe(f"{config.PUBSUB_PREFIX}:{channel_id}")
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
