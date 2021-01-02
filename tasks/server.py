import os
import re
import typing as t
import ansible_runner
from uuid import uuid4
from collections import defaultdict
from distutils.dir_util import copy_tree
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule
from app.db.crud.port import get_port_with_num
from app.db.crud.server import get_server, get_servers
from app.db.crud.port_usage import create_port_usage, edit_port_usage
from app.db.schemas.port_usage import PortUsageCreate, PortUsageEdit

from tasks import celery_app
from tasks.utils.runner import run_async, run
from tasks.utils.server import prepare_priv_dir
from tasks.utils.files import get_md5_for_file
from tasks.utils.handlers import update_facts, server_facts_event_handler


def finished_handler(server: Server, md5: str):
    def wrapper(runner):
        facts = runner.get_fact_cache(server.ansible_name)
        update_facts(server.id, facts, md5=md5)
    return wrapper


@celery_app.task()
def servers_runner(**kwargs):
    servers = get_servers(SessionLocal())
    init_md5 = get_md5_for_file("ansible/project/server.yml")
    for server in servers:
        if "init" not in server.config or server.config["init"] != init_md5:
            run(
                server=server,
                playbook="server.yml",
                extravars=kwargs,
                event_handler=server_facts_event_handler(server),
                finished_callback=finished_handler(server, init_md5),
            )


@celery_app.task()
def server_runner(server_id: int, **kwargs):
    init_md5 = get_md5_for_file("ansible/project/server.yml")
    server = get_server(SessionLocal(), server_id)
    run(server, init_md5, **kwargs)
