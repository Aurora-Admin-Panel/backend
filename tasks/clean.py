import time
import typing as t

from huey import crontab

from app.db.session import db_session
from app.db.crud.server import get_server_with_ports_usage
from app.db.crud.port_forward import get_forward_rule, get_all_expire_rules
from app.db.models.port import Port
from .config import huey
from tasks.ansible import ansible_hosts_runner
from tasks.utils.runner import run
from tasks.utils.handlers import iptables_finished_handler


def clean_finished_handler(runner):
    ansible_hosts_runner()


@huey.task()
def clean_runner(server: t.Dict):
    run(
        server=server,
        playbook="clean.yml",
        finished_callback=clean_finished_handler,
    )


@huey.task(priority=4)
def clean_port_runner(server_id: int, port: Port, update_traffic: bool = True):
    with db_session() as db:
        if db_forward_rule := get_forward_rule(db, server_id, port.id):
            db.delete(db_forward_rule)
            db.commit()
        server = get_server_with_ports_usage(db, server_id)
    run(
        server=server,
        playbook="clean_port.yml",
        extravars={"local_port": port.num},
        finished_callback=iptables_finished_handler(
            server.id, accumulate=True, update_traffic_bool=update_traffic
        ),
    )


@huey.periodic_task(crontab(minute="*"), priority=4)
def clean_expired_port_runner():
    with db_session() as db:
        db_expire_rules = get_all_expire_rules(db)
    for db_rule in db_expire_rules:
        if time.time() > db_rule.config.get("expire_time", float("inf")):
            clean_port_runner(
                db_rule.port.server.id,
                db_rule.port,
                update_traffic=True,
            )
