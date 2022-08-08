from huey import crontab
from fabric import Connection, Config

from app.core.config import TRAFFIC_INTERVAL_SECONDS
from app.db.session import db_session
from app.db.models.server import Server
from app.db.crud.server import get_server_with_ports_usage, get_servers

from .config import huey
from tasks.utils.runner import run
from tasks.utils.handlers import iptables_finished_handler


@huey.task()
def traffic_server_runner(server_id: int):
    with db_session() as db:
        server = get_server_with_ports_usage(db, server_id)
    run(
        server=server,
        playbook="traffic.yml",
        finished_callback=iptables_finished_handler(server.id),
    )


@huey.periodic_task(crontab(minute=f"*/{int(TRAFFIC_INTERVAL_SECONDS)//60}"))
def traffic_runner():
    with db_session() as db:
        servers = get_servers(db)
    for server in servers:
        traffic_server_runner(server.id)


@huey.task()
def traffic_server_runner2(server_id: int):
    with db_session() as db:
        server = get_server_with_ports_usage(db, server_id)
    config = {}
    if server.sudo_password:
        config["sudo"] = {"password": server.sudo_password}
    connect_kwargs = {}
    if server.ssh_password:
        connect_kwargs["password"] = server.ssh_password
    else:
        connect_kwargs["key_filename"] = "/app/ansible/env/ssh_key"

    with Connection(
        host=server.ansible_host,
        user=server.ansible_user,
        port=server.ansible_port,
        connect_kwargs=connect_kwargs,
        config=Config(overrides=config),
    ) as c:
        result = c.put("/app/ansible/project/files/iptables.sh")
        print(result)
        result = c.sudo("iptables.sh list_all")
        print(result.stdout.strip())