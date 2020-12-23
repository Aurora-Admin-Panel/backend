import json
import typing as t
import ansible_runner
from uuid import uuid4

from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule
from app.db.crud.server import get_server
from app.db.crud.port import get_port

from tasks import celery_app
from tasks.utils.runner import run
from tasks.utils.handlers import iptables_finished_handler, status_handler


@celery_app.task()
def reverse_proxy_runner(
    server_id: int
):
    server = get_server(SessionLocal(), server_id)

    extravars = {
        "host": server.ansible_name,
    }
    r = run(
        server=server,
        playbook="test.yml",
        extravars=extravars,
    )
    return r[1].config.artifact_dir
