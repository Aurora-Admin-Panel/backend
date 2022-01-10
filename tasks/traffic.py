from huey import crontab

from app.core.config import TRAFFIC_INTERVAL_SECONDS
from app.db.session import db_session
from app.db.models.server import Server
from app.db.crud.server import get_server_with_ports_usage, get_servers

from .config import huey
from tasks.utils.runner import run
from tasks.utils.handlers import iptables_finished_handler


@huey.task(priority=6)
def traffic_server_runner(server_id: Server):
    with db_session() as db:
        server = get_server_with_ports_usage(db, server_id)
    return run(
        server=server,
        playbook="traffic.yml",
        finished_callback=iptables_finished_handler(server),
    )


@huey.periodic_task(crontab(minute=f"*/{int(TRAFFIC_INTERVAL_SECONDS)//60}"))
def traffic_runner():
    with db_session() as db:
        servers = get_servers(db)
    for server in servers:
        traffic_server_runner(server.id)
