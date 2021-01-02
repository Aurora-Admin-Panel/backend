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
from app.db.schemas.server import ServerEdit
from app.db.schemas.port_usage import PortUsageCreate, PortUsageEdit

from tasks import celery_app
from tasks.utils.runner import run, run_async
from tasks.utils.handlers import iptables_finished_handler


@celery_app.task()
def traffic_server_runner(server_id: Server):
    server = get_server(SessionLocal(), server_id)
    return run(
        server=server,
        playbook="traffic.yml",
        finished_callback=iptables_finished_handler(server),
    )


@celery_app.task()
def traffic_runner():
    servers = get_servers(SessionLocal())
    for server in servers:
        traffic_server_runner.delay(server.id)
