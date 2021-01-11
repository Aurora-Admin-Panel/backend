from app.db.session import get_db
from app.db.models.server import Server
from app.db.crud.server import get_server, get_servers

from tasks import celery_app
from tasks.utils.runner import run
from tasks.utils.handlers import iptables_finished_handler


@celery_app.task(priority=6)
def traffic_server_runner(server_id: Server):
    server = get_server(next(get_db()), server_id)
    return run(
        server=server,
        playbook="traffic.yml",
        finished_callback=iptables_finished_handler(server),
    )


@celery_app.task()
def traffic_runner():
    servers = get_servers(next(get_db()))
    for server in servers:
        traffic_server_runner.delay(server.id)
