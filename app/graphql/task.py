import json
import asyncio
from typing import AsyncGenerator

from strawberry.scalars import JSON

import tasks
from app.core import config, codec
from app.core.redis_client import new_pubsub_redis
from app.core.redis_keyspace import Keys


async def task(name: str, xargs: JSON) -> AsyncGenerator[JSON, None]:
    task_func = getattr(tasks, name, None)
    if not task_func:
        yield {"error": f"Task '{name}' not found"}
        return

    result = task_func(**json.loads(xargs))
    while True:
        res = result.get()
        if res is not None:
            break
        await asyncio.sleep(0.1)
    yield res


def _extract_text(raw: str) -> str:
    try:
        obj = codec.loads(raw)
        if isinstance(obj, dict) and "text" in obj:
            return str(obj["text"])
    except Exception:
        pass
    return raw


async def task_stream(
    task_id: str,
    *,
    block_seconds: int | None = None,
    backfill: bool = True,
    batch_size: int = 1000,
) -> AsyncGenerator[JSON, None]:
    key = Keys.task_stream(task_id)
    conn = new_pubsub_redis()
    last_id = "0-0" if backfill else "$"  # ← only valid tokens for XREAD

    block_ms = int((block_seconds or config.PUBSUB_TIMEOUT_SECONDS) * 1000)
    try:
        while True:
            # Read a batch (backlog first; then blocks waiting for new items)
            streams = await conn.xread({key: last_id}, block=block_ms, count=batch_size)
            print(streams)
            if not streams:
                await asyncio.sleep(config.PUBSUB_TIMEOUT_SECONDS)
                continue

            _, entries = streams[0]
            for entry_id, fields in entries:
                last_id = entry_id
                raw = fields.get("payload") or fields.get("data") or ""
                text = _extract_text(raw)
                if text == config.PUBSUB_STOPWORD:
                    return
                yield {"type": "message", "data": text}

            # Optional fast-drain: clear any remaining backlog without blocking
            while True:
                more = await conn.xread({key: last_id}, block=0, count=batch_size)
                if not more:
                    break
                _, entries = more[0]
                for entry_id, fields in entries:
                    last_id = entry_id
                    raw = fields.get("payload") or fields.get("data") or ""
                    text = _extract_text(raw)
                    if text == config.PUBSUB_STOPWORD:
                        return
                    yield {"type": "message", "data": text}
    finally:
        try:
            await conn.close()
        except Exception:
            pass
