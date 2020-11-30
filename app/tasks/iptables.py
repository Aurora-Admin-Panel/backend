import os
import ansible_runner
from uuid import uuid4
from distutils.dir_util import copy_tree

from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.crud.server import get_server, get_servers
from app.db.models.port_forward import PortForwardRule

from . import celery_app
from .utils import prepare_priv_dir, iptables_finished_handler



@celery_app.task()
def forward_rule_status_handler(
    port_id: int, status_data: dict, update_status: bool
):
    if not update_status:
        return status_data
    db = SessionLocal()
    rule = (
        db.query(PortForwardRule)
        .filter(PortForwardRule.port_id == port_id)
        .first()
    )
    if rule:
        if (
            status_data.get("status", None) == "starting"
            and rule.status == "running"
        ):
            return status_data
        rule.status = status_data.get("status", None)
        db.add(rule)
        db.commit()
    return status_data


@celery_app.task()
def iptables_runner(
    port_id: int,
    server_id: int,
    local_port: int,
    remote_ip: str = None,
    remote_port: int = None,
    forward_type: str = None,
    update_status: bool = False,
):
    server = get_server(SessionLocal(), server_id)
    priv_data_dir = prepare_priv_dir(server)
    if not forward_type:
        args = f" delete {local_port}"
    elif remote_ip and remote_port:
        args = f" -t={forward_type} forward {local_port} {remote_ip} {remote_port}"
    else:
        args = f" list {local_port}"
    extra_vars = {
        "host": server.ansible_name,
        "local_port": local_port,
        "iptables_args": args,
    }

    t = ansible_runner.run_async(
        private_data_dir=priv_data_dir,
        project_dir="ansible/project",
        playbook="iptables.yml",
        extravars=extra_vars,
        status_handler=lambda s, **k: forward_rule_status_handler.delay(
            port_id, s, update_status
        ),
        finished_callback=iptables_finished_handler(server, True),
    )
    return t[1].config.artifact_dir


@celery_app.task()
def iptables_reset_runner(
    server_id: int,
    port_num: int,
):
    server = get_server(SessionLocal(), server_id)
    priv_data_dir = prepare_priv_dir(server)
    extra_vars = {
        "host": server.ansible_name,
        "local_port": port_num,
        "iptables_args": f" reset {port_num}",
    }

    t = ansible_runner.run_async(
        private_data_dir=priv_data_dir,
        project_dir="ansible/project",
        playbook="iptables.yml",
        extravars=extra_vars,
    )
    return t[1].config.artifact_dir
