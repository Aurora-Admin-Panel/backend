import json
import asyncio
from typing import AsyncGenerator

from strawberry.scalars import JSON

import tasks


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
