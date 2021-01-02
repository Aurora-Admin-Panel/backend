import json
import ansible_runner
from uuid import uuid4

from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.crud.server import get_server
from app.db.models.port_forward import PortForwardRule

from tasks import celery_app
from tasks.utils.runner import run_async, run
from tasks.utils.handlers import update_facts


def finished_handler(server: Server):
    def wrapper(runner):
        update_facts(server.id, runner.get_fact_cache(server.ansible_name))
    return wrapper
        

@celery_app.task(priority=3)
def connect_runner(
    server_id: int,
):
    server = get_server(SessionLocal(), server_id)
    return run(
        server=server,
        playbook="connect.yml",
        finished_callback=finished_handler(server),
    )
