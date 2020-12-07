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

from . import celery_app
from .runner import run_async
from .utils import iptables_finished_handler, status_handler, update_facts, update_rule_error


def finished_handler(server: Server, server_id: int, port_id: int):
    def wrapper(runner):
        facts = runner.get_fact_cache(server.ansible_name)
        if facts:
            update_facts(server.id, facts)
            if facts.get('error'):
                update_rule_error(server_id, port_id, facts.get('error')) 
        iptables_finished_handler(server, True)
    return wrapper


@celery_app.task()
def gost_runner(
    port_id: int,
    server_id: int,
    port_num: int,
    gost_config: t.Dict,
    remote_ip: str = None,
    update_status: bool = False,
):
    server = get_server(SessionLocal(), server_id)
    with open(f"ansible/project/roles/gost/files/{port_id}.json", "w") as f:
        f.write(json.dumps(gost_config, indent=4))

    extravars = {
        "host": server.ansible_name,
        "port_id": port_id,
        "local_port": port_num,
        "remote_ip": remote_ip,
        "update_status": update_status,
        "update_gost": update_status and not server.config.get('gost'),
    }
    r = run_async(
        server=server,
        playbook="gost.yml",
        extravars=extravars,
        status_handler=lambda s, **k: status_handler(port_id, s, update_status),
        finished_callback=finished_handler(server, server_id, port_id)
        if update_status
        else lambda r: None,
    )
    return r[1].config.artifact_dir
