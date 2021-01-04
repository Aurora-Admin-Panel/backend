import json
import typing as t
import ansible_runner
from uuid import uuid4

from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule, MethodEnum
from app.db.crud.server import get_server
from app.db.crud.port import get_port_by_id
from app.db.crud.port_forward import get_forward_rule_by_id
from app.utils.caddy import generate_caddy_config
from app.utils.v2ray import generate_v2ray_config
from tasks import celery_app
from tasks.utils.runner import run_async
from tasks.utils.handlers import iptables_finished_handler


def clean_finished_handler(runner):
    celery_app.send_task("tasks.ansible.ansible_hosts_runner")


@celery_app.task()
def clean_runner(server: t.Dict):
    t = run_async(
        server=server,
        playbook="clean.yml",
        finished_callback=clean_finished_handler,
    )
    return t[1].config.artifact_dir


@celery_app.task()
def clean_port_runner(server_id: int, port_num: int):
    server = get_server(SessionLocal(), server_id)
    t = run_async(
        server=server,
        playbook="clean_port.yml",
        extravars={"local_port": port_num},
        finished_callback=iptables_finished_handler(server, accumulate=True),
    )
    return t[1].config.artifact_dir