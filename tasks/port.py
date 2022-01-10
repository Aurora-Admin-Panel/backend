import typing as t

from app.db.session import db_session
from app.db.crud.server import get_server_with_ports_usage
from .config import huey
from tasks.utils.runner import run


@huey.task()
def clean_port_no_update_runner(
    server_id: int, port_num: int, update_traffic: bool = True
):
    with db_session() as db:
        server = get_server_with_ports_usage(db, server_id)
    run(
        server=server,
        playbook="clean_port.yml",
        extravars={"local_port": port_num},
    )