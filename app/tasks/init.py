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

from . import celery_app
from .utils import prepare_priv_dir, iptables_finished_handler, get_md5_for_file


def finished_handler(server: Server, md5: str):
    def wrapper(runner):
        db = SessionLocal()
        db_server = get_server(db, server.id)
        db_server.config['facts'] = runner.get_fact_cache(server.ansible_name)
        db_server.config['init'] = md5
        db.add(db_server)
        db.commit()
    return wrapper


@celery_app.task()
def server_init_runner(
    server_id: int = None
):
    servers = get_servers(SessionLocal())
    init_md5 = get_md5_for_file('ansible/project/roles/server_init/tasks/main.yml')
    for server in servers:
        if server.id == server_id or 'init' not in server.config or server.config['init'] != init_md5:
            priv_data_dir = prepare_priv_dir(server)
            ansible_runner.run_async(
                private_data_dir=priv_data_dir,
                project_dir="ansible/project",
                playbook="server_init.yml",
                extravars={"host": server.ansible_name},
                finished_callback=finished_handler(server, init_md5),
            )
