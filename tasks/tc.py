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
from tasks.utils.runner import run_async


@celery_app.task()
def tc_runner(
    server_id: int,
    port_num: int,
    egress_limit: int = None,
    ingress_limit: int = None
):
    server = get_server(SessionLocal(), server_id)
    args = ""
    if egress_limit:
        args += f' -e={egress_limit}kbit'
    if ingress_limit:
        args += f' -i={ingress_limit}kbit'
    args += f' {port_num}'

    t = run_async(
        server=server,
        playbook="tc.yml",
        extravars={"host": server.ansible_name, "tc_args": args},
    )
    return t[1].config.artifact_dir
