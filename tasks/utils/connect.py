import socket
import pathlib
import traceback
from datetime import datetime, UTC
from contextlib import contextmanager
from collections.abc import Iterator

from loguru import logger
from sqlalchemy import update
from fabric import Config
from fabric.exceptions import GroupException
from paramiko.ssh_exception import SSHException


from app.core import config
from app.db.models import Server
from app.db.crud.server import get_server
from app.db.session import db_session

from tasks.utils.exception import AuroraException
from tasks.utils.connection import AuroraConnection


@contextmanager
def connect(server_id: int, **kwargs) -> Iterator[AuroraConnection]:
    with db_session() as db:
        server = get_server(db, server_id)

    if not server:
        raise AuroraException(f"Server with id {server_id} does not exist")

    connect_kwargs = {}
    if server.ssh_password:
        connect_kwargs["password"] = server.ssh_password
    if server.key_file:
        connect_kwargs["key_filename"] = server.key_file.storage_path
    elif (
        not server.ssh_password
        and not server.key_file
        and pathlib.Path("/app/ansible/env/ssh_key").is_file()
    ):
        connect_kwargs["key_filename"] = "/app/ansible/env/ssh_key"

    connection_config = {}
    if server.sudo_password:
        connection_config["sudo"] = {"password": server.sudo_password}

    try:
        conn = AuroraConnection(
            host=server.host,
            user=server.user,
            port=server.port,
            connect_timeout=config.SSH_CONNECTION_TIMEOUT,
            connect_kwargs=connect_kwargs,
            config=Config(overrides=connection_config),
            task=kwargs.pop("task", None),
            **kwargs,
        )
        conn.check_sudo()
        yield conn

        with db_session() as db:
            if s := db.get(Server, server_id):
                s.last_seen = datetime.now(UTC)
                db.commit()
    except GroupException as e:
        raise AuroraException(f"[{server.name}] Failed to connect to host: {e}")
    except (socket.timeout, TimeoutError) as e:
        raise AuroraException(f"[{server.name}] Connection timed out: {e}")
    except socket.error as e:
        raise AuroraException(f"[{server.name}] Socket error: {e}")
    except SSHException as e:
        raise AuroraException(f"[{server.name}] SSH error: {e}")
    except Exception as e:
        logger.exception(e)
        raise AuroraException(f"[{server.name}] Failed to connect to host: {e}")
    finally:
        conn.close()
