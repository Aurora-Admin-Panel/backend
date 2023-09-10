import asyncio
import threading
from typing import Awaitable, Callable, Dict, Any
from collections import defaultdict


def run_in_thread(corofn: Awaitable, *args):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(corofn(*args))
    loop.close()
