import typing as t

from app.db.session import db_session
from app.db.crud.server import get_server_with_ports_usage
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
def clean_port_runner(
    server_id: int, port_num: int, update_traffic: bool = True
):
    with db_session() as db:
        server = get_server_with_ports_usage(db, server_id)
    run(
        server=server,
        playbook="clean_port.yml",
        extravars={"local_port": port_num},
        finished_callback=iptables_finished_handler(
            server.id, accumulate=True, update_traffic_bool=update_traffic
        ),
    )
