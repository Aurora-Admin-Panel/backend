from app.db.session import db_session
from app.db.models.server import Server
from app.db.crud.server import get_server_with_ports_usage, get_servers, get_servers2

from tasks import celery_app
from tasks.utils.runner import run
from tasks.utils.handlers import iptables_finished_handler


@celery_app.task(priority=6)
def traffic_server_runner(server_id: Server):
    with db_session() as db:
        server = get_server_with_ports_usage(db, server_id)
    return run(
        server=server,
        playbook="traffic.yml",
        finished_callback=iptables_finished_handler(server),
    )


@celery_app.task()
def traffic_runner():
    with db_session() as db:
        servers = get_servers2(db)
    for server in servers:
        traffic_server_runner.delay(server.id)
