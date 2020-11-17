import os
import re
import typing as t
import ansible_runner
from uuid import uuid4
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
from .utils import prepare_priv_dir


def update_usage(
    db: Session,
    prev_ports: t.Dict,
    db_ports: t.Dict,
    server_id: int,
    dir: str,
    port_num: int,
    usage: int,
):
    if port_num not in db_ports:
        db_port = get_port_with_num(db, server_id, port_num)
        if not db_port:
            print(f"Port not found, num: {port_num}, server_id: {server_id}")
            return
        if not db_port.usage:
            create_port_usage(db, db_port.id, PortUsageCreate())
            db.refresh(db_port)
        db_ports[port_num] = db_port

    if port_num not in prev_ports or not prev_ports[port_num].usage:
        edit_port_usage(db, db_ports[port_num].id, PortUsageEdit(**{f"{dir}": usage}))
    else:
        if getattr(prev_ports[port_num].usage, f'{dir}_checkpoint') != getattr(db_ports[port_num].usage, f'{dir}_checkpoint'):
            print(f"checkpoint mismatch, aborting. Prev checkpoint: {getattr(prev_ports[port_num].usage, f'{dir}_checkpoint')}, current checkpoint: {getattr(db_ports[port_num].usage, f'{dir}_checkpoint')}")
        else:
            pass


def finished_handler(server):
    def wrapper(runner):
        db = SessionLocal()
        download_pattern = re.compile(r"\/\* UPLOAD ([0-9]+)->")
        upload_pattern = re.compile(r"\/\* DOWNLOAD ([0-9]+)->")
        prev_ports = {port.num: port for port in server.ports}
        db_ports = {}
        print(
            f"{server.ansible_name}: {runner.get_fact_cache(server.ansible_name)}"
        )
        for line in (
            runner.get_fact_cache(server.ansible_name)
            .get("result", "")
            .split("\n")
        ):
            match = download_pattern.search(line)
            if (
                match
                and len(match.groups()) > 0
                and match.groups()[0].isdigit()
            ):
                port_num = int(match.groups()[0])
                update_usage(
                    db,
                    prev_ports,
                    db_ports,
                    server.id,
                    "download",
                    port_num,
                    int(line.split()[1]),
                )
            match = upload_pattern.search(line)
            if (
                match
                and len(match.groups()) > 0
                and match.groups()[0].isdigit()
            ):
                port_num = int(match.groups()[0])
                update_usage(
                    db,
                    prev_ports,
                    db_ports,
                    server.id,
                    "upload",
                    port_num,
                    int(line.split()[1]),
                )
    return wrapper


@celery_app.task()
def bandwidth_runner():
    servers = get_servers(SessionLocal())
    for server in servers:
        priv_data_dir = prepare_priv_dir(server)
        ansible_runner.run_async(
            private_data_dir=priv_data_dir,
            project_dir="ansible/project",
            playbook="bandwidth.yml",
            extravars={"host": server.ansible_name},
            finished_callback=finished_handler(server),
        )
