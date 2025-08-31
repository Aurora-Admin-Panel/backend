import os
import re
import typing as t
from uuid import uuid4
from datetime import datetime, timedelta, UTC
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import insert, select, delete
from huey import crontab
from huey.api import Result, Task
from loguru import logger
from websockets.connection import SERVER

from app.core.redis_keyspace import Keys
from app.core.config import SERVER_USAGE_INTERVAL_SECONDS
from app.db.session import db_session
from app.db.models import Server
from app.db.crud.server import get_server, get_servers

from .config import huey
from tasks.utils.interval import compute_exponential_backoff, jitter
from tasks.utils.files import get_md5_for_file
from tasks.utils.handlers import update_facts as update_facts_old
from tasks.utils.connect import connect
from tasks.utils.metric import build_metric_models
from tasks.utils.server import update_facts
from tasks.utils.redis_client import get_redis
from tasks.utils.exception import AuroraException
from tasks.utils.orchestrator import SystemOrchestrator


def finished_handler(server_id: int, md5: str = None):
    def wrapper(runner):
        with db_session() as db:
            server = get_server(db, server_id)
        facts = runner.get_fact_cache(server.host)
        update_facts_old(server.id, facts, md5=md5)

    return wrapper


# @huey.task(priority=3)
# def server_runner(server_id: int, **kwargs):
#     init_md5 = get_md5_for_file("ansible/project/server.yml")
#     with db_session() as db:
#         server = get_server(db, server_id)
#     run(
#         server=server,
#         playbook="server.yml",
#         extravars=kwargs,
#         event_handler=server_facts_event_handler(server.id),
#         finished_callback=finished_handler(server.id, init_md5),
#     )


# @huey.task(priority=3)
# def connect_runner(
#     server_id: int,
# ):
#     with db_session() as db:
#         server = get_server(db, server_id)
#     run(
#         server=server,
#         playbook="connect.yml",
#         event_handler=server_facts_event_handler(server.id),
#         finished_callback=finished_handler(server.id),
#     )


@huey.task(priority=3, context=True)
def connect_runner2(server_id: int, task: Task):
    try:
        with connect(server_id=server_id, task=task):
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
            pass
            # server_runner(server.id, **kwargs)


@huey.task(priority=10, context=True)
def server_usage_runner(server_id: int, task: Task):
    try:
        with connect(server_id=server_id, task=task) as c:
            task_result = (
                SystemOrchestrator(c).system_info(f"system-info-{server_id}").execute()
            )
            if info := next(
                (
                    o
                    for o in task_result.results
                    if o.success and o.name == f"system-info-{server_id}"
                ),
                None,
            ):
                with db_session() as db:
                    server = get_server(db, server_id)
                    snapshot = build_metric_models(info.details, server_id)
                    update_facts(db, server, snapshot.facts)
                    db.add(snapshot.metric)
                    db.add_all(snapshot.disks)
                    db.add_all(snapshot.ifaces)
                    db.commit()
            else:
                logger.warning(
                    f"Failed to get system info for server {server_id}: {task_result}"
                )
    except AuroraException as e:
        logger.debug(str(e))
    except Exception as e:
        # TODO: handle exception
        logger.exception(e)
    finally:
        last_seen = None
        with db_session() as db:
            server = get_server(db, server_id)
            if not server:
                return
            last_seen = server.last_seen
        delay = compute_exponential_backoff(last_seen, SERVER_USAGE_INTERVAL_SECONDS)
        logger.debug(
            f"Scheduling server_usage_runner for server {server.name} with delay {delay} seconds"
        )
        res: Result = server_usage_runner.schedule(args=(server_id,), delay=delay)
        with get_redis() as r:
            if existing_task_id := r.get(Keys.server_usage_task(server.id)):
                huey.revoke_by_id(existing_task_id)
            r.set(Keys.server_usage_task(server.id), res.id)


@huey.task(priority=1)
def servers_usage_runner():
    with db_session() as db:
        servers = db.query(Server).filter(Server.is_active.is_(True)).all()
        for server in servers:
            with get_redis() as r:
                if not r.get(Keys.server_usage_task(server.id)):
                    logger.debug(
                        f"Starting server_usage_runner for server {server.name} in "
                        f"{SERVER_USAGE_INTERVAL_SECONDS} seconds"
                    )
                    delay = jitter(SERVER_USAGE_INTERVAL_SECONDS, "30%")
                    res: Result = server_usage_runner.schedule(
                        args=(server.id,), delay=delay
                    )
                    r.set(Keys.server_usage_task(server.id), res.id)


SCRIPT = """
P=/usr/local/aurora/system_probe.sh;
if [ -f "$P" ]; then
printf 'exists\\t1\\n';
# stat (GNU first, then BSD/macOS)
if stat -c '%a %U %G' "$P" >/dev/null 2>&1; then
    set -- $(stat -c '%a %U %G' "$P");
else
    set -- $(stat -f '%Lp %Su %Sg' "$P");
fi
printf 'mode\\t%s\\nowner\\t%s\\ngroup\\t%s\\n' "$1" "$2" "$3";

# checksum (md5sum, then md5, then openssl)
if command -v md5sum >/dev/null 2>&1; then
    C=$(md5sum "$P" | awk '{{print $1}}');
elif command -v md5 >/dev/null 2>&1; then
    C=$(md5 -q "$P");
elif command -v openssl >/dev/null 2>&1; then
    C=$(openssl md5 -r "$P" | awk '{{print $1}}');
else
    C="";
fi
printf 'checksum\\t%s\\n' "$C";
else
printf 'exists\\t0\\n';
fi
    """


@huey.task(priority=1)
def server_test_runner2():
    from loguru import logger
    from fabric import Connection, Config
    from tasks.utils.helper import q
    from tasks.utils.connection import AuroraConnection
    from tasks.utils.connect import connect
    from tasks.utils.files import FileResource
    from tasks.utils.orchestrator import SystemOrchestrator

    # connect_kwargs = {"key_filename": "/app/ansible/env/ssh_key"}
    # connection_config = {"sudo": {"password": "2143wq"}}
    # conn = AuroraConnection(
    #     host="hk2.leishi.io",
    #     user="lei",
    #     connect_kwargs=connect_kwargs,
    #     config=Config(overrides=connection_config),
    # )
    # conn.check_sudo()
    with connect(server_id=204) as conn:
        orch = SystemOrchestrator(conn)
        res = orch.system_info().execute()
        logger.info(res)


@huey.task(priority=1, context=True)
def servers_test_runner(task: Task):
    with connect(server_id=204) as c:
        orch = SystemOrchestrator(c)
        # res = orch.system_info().execute()
        res = orch.ensure_file(
            "check system_probe.sh",
            path="/usr/local/aurora/system_probe.sh",
            src="/app/files/system_probe.sh",
            mode="0755",
        ).execute()
        logger.info(res)
    # logger.info("Starting servers_test_runner")
    # with db_session() as db:
    #     hk2 = db.query(Server).filter(Server.address == "hk2.leishi.io").one()
    #     logger.info(f"Testing server {hk2.name}")
    #     with connect(204, task=task) as c:
    #         count = 0
    #         import time

    #         while True:
    #             logger.info(f"Running test {count}")
    #             c.run(f"echo {count}")
    #             count += 1
    #             time.sleep(1)
    #             if count > 60 * 10:
    #                 break


@huey.periodic_task(crontab(day="*"))
def server_usage_cleaner():
    pass
    # with db_session() as db:
    #     stmt = delete(ServerUsage).where(
    #         ServerUsage.timestamp < datetime.now(UTC) - timedelta(days=30)
    #     )
    #     db.execute(stmt)
    #     db.commit()
