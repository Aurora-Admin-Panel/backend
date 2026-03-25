from huey import crontab
from fabric import Connection, Config

from app.core.config import TRAFFIC_INTERVAL_SECONDS
from app.db.session import db_session
from app.db.models import Server
from app.db.crud.server import get_server_with_ports_usage, get_servers

from .config import huey
from tasks.utils.runner import run
from tasks.utils.handlers import iptables_finished_handler
from tasks.utils.connection import connect


@huey.task()
def traffic_server_runner(server_id: int):
    with db_session() as db:
        server = get_server_with_ports_usage(db, server_id)
    run(
        server=server,
        playbook="traffic.yml",
        finished_callback=iptables_finished_handler(server.id),
    )


@huey.periodic_task(crontab(minute=f"*/{int(TRAFFIC_INTERVAL_SECONDS)//60}"))
def traffic_runner():
    with db_session() as db:
        servers = get_servers(db)
    for server in servers:
        traffic_server_runner(server.id)



@huey.task()
def traffic_server_runner2(server_id: int):
    with db_session() as db:
        server = get_server_with_ports_usage(db, server_id)

    with connect(server_id=server_id) as c:
        result = c.put("/app/ansible/project/files/iptables.sh")
        print(result)
        result = c.run("iptables.sh list_all")
        print(result.stdout.strip())
