import os
import ansible_runner
from uuid import uuid4
from distutils.dir_util import copy_tree

from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.crud.server import get_server, get_servers
from app.db.crud.port_forward import get_all_iptables_rules
from app.db.models.port_forward import PortForwardRule
from app.utils.dns import dns_query
from app.utils.ip import is_ip

from tasks import celery_app
from tasks.utils.runner import run_async
from tasks.utils.server import prepare_priv_dir
from tasks.utils.handlers import status_handler, iptables_finished_handler


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
    if not forward_type:
        args = f" delete {local_port}"
    elif remote_ip and remote_port:
        args = (
            f" -t={forward_type} forward {local_port} {remote_ip} {remote_port}"
        )
    else:
        args = f" list {local_port}"
    extravars = {
        "host": server.ansible_name,
        "local_port": local_port,
        "iptables_args": args,
    }

    t = run_async(
        server=server,
        playbook="iptables.yml",
        extravars=extravars,
        status_handler=lambda s, **k: status_handler(port_id, s, update_status),
        finished_callback=iptables_finished_handler(server, port_id, True)
        if update_status
        else lambda r: None,
    )
    return t[1].config.artifact_dir


@celery_app.task()
def iptables_reset_runner(
    server_id: int,
    port_num: int,
):
    server = get_server(SessionLocal(), server_id)
    extravars = {
        "host": server.ansible_name,
        "local_port": port_num,
        "iptables_args": f" reset {port_num}",
    }

    t = run_async(
        server=server,
        playbook="iptables.yml",
        extravars=extravars,
    )
    return t[1].config.artifact_dir


@celery_app.task()
def ddns_runner():
    rules = get_all_iptables_rules(SessionLocal())
    for rule in rules:
        if (
            rule.config.get("remote_address")
            and rule.config.get("remote_ip")
            and not is_ip(rule.config.get("remote_address"))
        ):
            updated_ip = dns_query(rule.config["remote_address"])
            if updated_ip != rule.config["remote_ip"]:
                print(
                    f"DNS changed for address {rule.config['remote_address']}, "
                    + f"{rule.config['remote_ip']}->{updated_ip}"
                )
                iptables_runner.delay(
                    rule.port.id,
                    rule.port.server.id,
                    rule.port.num,
                    remote_ip=updated_ip,
                    remote_port=rule.config["remote_port"],
                    forward_type=rule.config.get("type", "ALL"),
                    update_status=True,
                )
