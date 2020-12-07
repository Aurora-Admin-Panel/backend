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
from .runner import run_async
from .utils import prepare_priv_dir, get_md5_for_file, update_facts



def event_handler(server: Server):
    def wrapper(event):
        if (
            "event_data" in event
            and event["event_data"].get("task") == "Gathering Facts"
            and not event.get('event', '').endswith('start')
        ):
            res = event["event_data"].get("res", {})
            update_facts(server.id, res.get("ansible_facts") if "ansible_facts" in res else res)

    return wrapper


def finished_handler(server: Server, md5: str):
    def wrapper(runner):
        facts = runner.get_fact_cache(server.ansible_name)
        update_facts(server.id, facts, md5=md5)
    return wrapper


def run(server: Server, init_md5: str, **kwargs):
    run_async(
        server=server,
        playbook="server.yml",
        extravars=kwargs,
        event_handler=event_handler(server),
        finished_callback=finished_handler(server, init_md5),
    )


@celery_app.task()
def servers_runner(
    sync_scripts: bool = False,
    init_iptables: bool = False,
    update_gost: bool = False,
    update_v2ray: bool = False,
):
    servers = get_servers(SessionLocal())
    init_md5 = get_md5_for_file("ansible/project/server.yml")
    for server in servers:
        if "init" not in server.config or server.config["init"] != init_md5:
            run(
                server,
                init_md5,
                sync_scripts=sync_scripts,
                init_iptables=init_iptables,
                update_gost=update_gost,
                update_v2ray=update_v2ray,
            )


@celery_app.task()
def server_runner(
    server_id: int,
    sync_scripts: bool = False,
    init_iptables: bool = False,
    update_gost: bool = False,
    update_v2ray: bool = False,
):
    init_md5 = get_md5_for_file("ansible/project/server.yml")
    server = get_server(SessionLocal(), server_id)
    run(
        server,
        init_md5,
        sync_scripts=sync_scripts,
        init_iptables=init_iptables,
        update_gost=update_gost,
        update_v2ray=update_v2ray,
    )
