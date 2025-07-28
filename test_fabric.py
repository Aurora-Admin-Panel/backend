import asyncio

from fabric import Config
from tasks.utils.connection import AuroraConnection
from tasks.utils.systemd import SystemdService


async def async_main() -> None:
    connection_config = {}
    connection_config["sudo"] = {"password": "2143wq"}
    c = AuroraConnection(
        host="hk2.leishi.io",
        config=Config(overrides=connection_config),
    )
    c.check_sudo()
    systemd = SystemdService(c, "docker")
    print(systemd.status(lines=10))
    # print(systemd.journal(tail=10))
    print(systemd.is_active)
    print(systemd.is_enabled)


asyncio.run(async_main())
