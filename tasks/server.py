import os
import re
import typing as t
import ansible_runner
from uuid import uuid4
from collections import defaultdict
from distutils.dir_util import copy_tree
from sqlalchemy.orm import Session

from app.db.session import db_session
from app.db.models import Port
from app.db.models import User
from app.db.models import File
from app.db.models import Server
from app.db.models import PortForwardRule
from app.db.crud.port import get_port_with_num
from app.db.crud.server import get_server, get_servers
from app.db.crud.port_usage import create_port_usage, edit_port_usage
from app.db.schemas.port_usage import PortUsageCreate, PortUsageEdit

from .config import huey
from tasks.utils.runner import run_async, run
from tasks.utils.server import prepare_priv_dir
from tasks.utils.files import get_md5_for_file
from tasks.utils.handlers import update_facts, server_facts_event_handler
from tasks.utils.connection import connect
from tasks.utils.exception import AuroraException


def finished_handler(server_id: int, md5: str = None):
    def wrapper(runner):
        with db_session() as db:
            server = get_server(db, server_id)
        facts = runner.get_fact_cache(server.host)
        update_facts(server.id, facts, md5=md5)
    return wrapper


@huey.task(priority=3)
def server_runner(server_id: int, **kwargs):
    init_md5 = get_md5_for_file("ansible/project/server.yml")
    with db_session() as db:
        server = get_server(db, server_id)
    run(
        server=server,
        playbook="server.yml",
        extravars=kwargs,
        event_handler=server_facts_event_handler(server.id),
        finished_callback=finished_handler(server.id, init_md5),
    )


@huey.task(priority=3)
def connect_runner(
    server_id: int,
):
    with db_session() as db:
        server = get_server(db, server_id)
    run(
        server=server,
        playbook="connect.yml",
        event_handler=server_facts_event_handler(server.id),
        finished_callback=finished_handler(server.id),
    )


@huey.task(priority=3)
def connect_runner2(
    server_id: int,
):
    try:
        with connect(server_id=server_id) as c:
            c.run("cat /etc/os-release")
            return {"success": True}

    except AuroraException as e:
        return {"error": str(e)}
    except Exception as e:
        # TODO: handle exception
        return {"error": str(e)}


@huey.task(priority=2)
def servers_runner(**kwargs):
    with db_session() as db:
        servers = get_servers(db)
    init_md5 = get_md5_for_file("ansible/project/server.yml")
    for server in servers:
        if "init" not in server.config or server.config["init"] != init_md5:
            server_runner(server.id, **kwargs)
