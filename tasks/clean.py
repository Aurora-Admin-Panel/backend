import typing as t

from app.db.session import get_db
from app.db.crud.server import get_server
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
    server = get_server(next(get_db()), server_id)
    t = run_async(
        server=server,
        playbook="clean_port.yml",
        extravars={"local_port": port_num},
        finished_callback=iptables_finished_handler(server, accumulate=True),
    )
    return t[1].config.artifact_dir