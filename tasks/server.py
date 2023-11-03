import os
import re
import typing as t
import ansible_runner
from uuid import uuid4
from datetime import datetime, timedelta
from collections import defaultdict
from distutils.dir_util import copy_tree
from sqlalchemy.orm import Session
from sqlalchemy import insert, select, delete
from huey import crontab
from huey.api import Task
from loguru import logger

from app.core.config import SERVER_USAGE_INTERVAL_SECONDS
from app.db.session import db_session
from app.db.models import Port
from app.db.models import User
from app.db.models import File
from app.db.models import Server, ServerUsage
from app.db.models import PortForwardRule
from app.db.crud.port import get_port_with_num
from app.db.crud.server import get_server, get_servers
from app.db.crud.port_usage import create_port_usage, edit_port_usage
from app.db.schemas.port_usage import PortUsageCreate, PortUsageEdit

from .config import huey
from tasks.utils.interval import should_schedule_seconds
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


@huey.task(priority=3, context=True)
def connect_runner2(server_id: int, task: Task):
    try:
        with connect(server_id=server_id, task=task) as c:
            c.get_os_release()
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


@huey.task(priority=10, context=True)
def server_usage_runner(server_id: int, task: Task):
    try:
        with connect(server_id=server_id, task=task) as c:
            usages = c.get_combined_usage()
            with db_session() as db:
                stmt = insert(ServerUsage).values(
                    server_id=server_id,
                    timestamp=datetime.utcnow(),
                    cpu=usages[0],
                    memory=usages[1],
                    disk=usages[2],
                )
                db.execute(stmt)
                db.commit()
    except AuroraException as e:
        logger.error(str(e))
    except Exception as e:
        # TODO: handle exception
        logger.error(str(e))

@huey.periodic_task(crontab(minute="*"))
def servers_usage_runner():
    with db_session() as db:
        stmt = select(Server).where(Server.is_active == True)
        servers = db.execute(stmt).scalars().unique().all()
        for seconds in should_schedule_seconds(SERVER_USAGE_INTERVAL_SECONDS):
            for server in servers:
                server_usage_runner.schedule(args=(server.id,), delay=seconds)

@huey.periodic_task(crontab(day="*"))
def server_usage_cleaner():
    with db_session() as db:
        stmt = delete(ServerUsage).where(
            ServerUsage.timestamp < datetime.utcnow() - timedelta(days=30)
        )
        db.execute(stmt)
        db.commit()