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
from app.db.models.port_forward import PortForwardRule, MethodEnum
from app.db.crud.port import get_port_with_num
from app.db.crud.server import get_server, get_servers
from app.db.crud.port_forward import get_all_non_iptables_rules
from app.db.crud.port_usage import create_port_usage, edit_port_usage
from app.db.schemas.port_usage import PortUsageCreate, PortUsageEdit

from tasks import celery_app
from tasks.utils.runner import run_async
from tasks.utils.server import prepare_priv_dir
from tasks.utils.files import get_md5_for_file
from tasks.utils.handlers import update_facts, server_facts_event_handler


def finished_handler(server_id: int):
    def wrapper(runner):
        if runner.status == 'successful':
            db = SessionLocal()
            db_server = get_server(db, server_id)
            db_server.config["migration"] = 'aurora_service_migration'
            db.add(db_server)
            db.commit()
    return wrapper


def get_service_name(rule: PortForwardRule, num: int) -> str:
    if rule.method == MethodEnum.GOST or rule.method == MethodEnum.V2RAY:
        return f"{rule.method.value}@{num}"
    return f"{rule.method.value}-{num}"


@celery_app.task()
def migration_runner(**kwargs):
    servers = get_servers(SessionLocal())
    for server in servers:
        if server.config.get('migration') != 'aurora_service_migration':
            app_list = []
            for port in server.ports:
                if port.forward_rule and port.forward_rule.method != MethodEnum.IPTABLES:
                    app_list.append({"port": port.num, "service_name": get_service_name(port.forward_rule, port.num)})
            extravars = {
                "app_list": app_list
            }
            run_async(
                server=server,
                playbook="migration.yml",
                extravars=extravars,
                finished_callback=finished_handler(server.id)
            )