import json
import typing as t
import ansible_runner
from uuid import uuid4

from tasks import celery_app
from tasks.utils.runner import run_async


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
def clean_port_runner(server: t.Dict, port_num: int):
    t = run_async(
        server=server,
        playbook="clean_port.yml",
        extravars={"local_port": port_num},
        finished_callback=clean_finished_handler,
    )
    return t[1].config.artifact_dir