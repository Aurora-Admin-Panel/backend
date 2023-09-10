import asyncio

from fabric import Config, Connection, Result
from tasks.utils.connection import AuroraConnection


async def async_main() -> None:
    c = AuroraConnection(
        host="hk2.leishi.io",
    )
    c.put_file(
        "/home/lei/workspace/created/aurora/backend/worker.sh",
        "/usr/local/etc/aurora/worker.sh",
    )


asyncio.run(async_main())
