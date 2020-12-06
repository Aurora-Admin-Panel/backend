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
from .utils import prepare_priv_dir, iptables_finished_handler, get_md5_for_file


def update_facts(server_id: int, md5: str, facts: t.Dict):
    db = SessionLocal()
    db_server = get_server(db, server_id)
    if facts.get("ansible_os_family"):
        db_server.config["system"] = {
            "os_family": facts.get("ansible_os_family"),
            "architecture": facts.get("ansible_architecture"),
            "distribution": facts.get("ansible_distribution"),
            "distribution_version": facts.get("ansible_distribution_version"),
            "distribution_release": facts.get("ansible_distribution_release"),
        }
    elif facts.get("msg"):
        db_server.config["system"] = {"msg": facts.get("msg")}
    # TODO: Add disable feature
    if facts.get("iptables"):
        db_server.config["iptables"] = facts.get("iptables")
    if facts.get("gost"):
        db_server.config["gost"] = facts.get("gost")
    if facts.get("v2ray"):
        db_server.config["v2ray"] = facts.get("v2ray")
    db_server.config["init"] = md5
    db.add(db_server)
    db.commit()


def event_handler(server: Server, md5: str):
    def wrapper(event):
        if (
            "event_data" in event
            and event["event_data"].get("task") == "Gathering Facts"
            and not event.get('event', '').endswith('start')
        ):
            res = event["event_data"].get("res", {})
            update_facts(server.id, md5, res.get("ansible_facts") if "ansible_facts" in res else res)

    return wrapper


def finished_handler(server: Server, md5: str):
    def wrapper(runner):
        facts = runner.get_fact_cache(server.ansible_name)
        update_facts(server.id, md5, facts)
    return wrapper


def run(server: Server, init_md5: str, **kwargs):
    run_async(
        server=server,
        playbook="server.yml",
        extravars=kwargs,
        event_handler=event_handler(server, init_md5),
        finished_callback=finished_handler(server, init_md5),
    )


@celery_app.task()
def servers_runner(
    sync_scripts: bool = False,
    init_iptables: bool = False,
    update_gost: bool = False,
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
            )


@celery_app.task()
def server_runner(
    server_id: int,
    sync_scripts: bool = False,
    init_iptables: bool = False,
    update_gost: bool = False,
):
    init_md5 = get_md5_for_file("ansible/project/server.yml")
    server = get_server(SessionLocal(), server_id)
    run(
        server,
        init_md5,
        sync_scripts=sync_scripts,
        init_iptables=init_iptables,
        update_gost=update_gost,
    )
