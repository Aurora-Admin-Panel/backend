import os
import time
import socket
import pathlib
import traceback
from uuid import uuid4
from decimal import Decimal
from typing import ContextManager, Tuple
from datetime import datetime
from contextlib import contextmanager

import redis
from loguru import logger
from fabric import Config, Connection, Result
from fabric.exceptions import GroupException
from paramiko.rsakey import RSAKey

from app.core import config
from app.db.crud.server import get_server
from app.db.session import db_session
from tasks.utils.exception import AuroraException
from tasks.utils.files import get_md5_for_file


class AuroraConnection(Connection):
    def __init__(self, *args, **kwargs):
        self._set(task=kwargs.pop("task", None))
        self._set(
            redis=redis.StrictRedis(
                host=config.REDIS_HOST, port=config.REDIS_PORT
            )
        )

        if self.task:
            self.redis.zadd(
                "aurora:task:ids",
                {self.task.id: datetime.utcnow().timestamp()},
            )
        super().__init__(*args, **kwargs)

    @property
    def sudo(self):
        return self.user != "root"

    def exists(self, path: str) -> bool:
        cmd = 'test -e "$(echo {})"'.format(path)
        return self._root_run(cmd, hide=True, warn=True).ok

    def get_os_release(self):
        return self.run(
            "grep -E '^(NAME|VERSION_ID)=' /etc/os-release | awk -F= '{ print $2 }' | tr -d '\"' | paste -sd ' ' -"
        ).strip()

    def get_cpu_usage(self):
        return self.run(
            "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage}'"
        ).strip()

    def get_memory_usage(self):
        return self.run("free | awk '/Mem:/ {print $3/$2 * 100.0}'").strip()

    def get_disk_usage(self):
        return self.run("df --output=pcent / | tail -1").strip("%")

    def get_combined_usage(self) -> Tuple[Decimal, Decimal, Decimal]:
        result = list(
            filter(
                lambda x: x,
                (
                    self.run(
                        'echo "'
                        "$(grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage}') "
                        "$(free | awk '/Mem:/ {print $3/$2 * 100.0}') "
                        '$(df --output=pcent / | tail -1)"'
                    ).split(" ")
                ),
            )
        )
        return (
            Decimal(result[0]),
            Decimal(result[1]),
            Decimal(result[2].strip("%")),
        )

    def close(self):
        if self.task:
            # Sleep for a bit so that stopword score is slightly larger
            time.sleep(0.1)
            self.publish(config.PUBSUB_STOPWORD)
        self.redis.close()
        super().close()

    def publish(self, text: str):
        if self.task:
            self.redis.publish(f"{config.PUBSUB_PREFIX}:{self.task.id}", text)
            self.redis.zadd(
                f"{config.PUBSUB_PREFIX}:{self.task.id}:history",
                {text: datetime.utcnow().timestamp()},
            )

    def _root_run(self, *args, **kwargs) -> Result:
        # Hacky and maybe buggy
        # when we actually want to use 'sudo' specific args
        if self.sudo:
            return super().sudo(*args, pty=True, **kwargs)
        else:
            return super().run(*args, pty=True, **kwargs)

    def run(self, *args, publish: bool = True, **kwargs) -> str:
        result = self._root_run(*args, hide=True, **kwargs)
        # stdout and stderr should already combined because the
        # behavior of pty=True
        stdout = result.stdout.strip("[sudo] password:").strip()
        if publish:
            self.publish(stdout)
        return stdout

    def mktemp(self) -> str:
        return super().run("mktemp", hide=True).stdout.strip()

    def ensure_folder(self, path: str) -> Result:
        # TODO: might need to check if path exists first
        self._root_run(f"mkdir -p {path}")

    def put_file(
        self, local_path: str, remote_path: str, ensure_same: bool = True
    ) -> None:
        if not pathlib.Path(local_path).exists():
            raise AuroraException(f"{local_path} does not exist")

        if self.exists(remote_path):
            if ensure_same:
                local_md5 = get_md5_for_file(local_path)
                remote_md5 = self.run(f"md5sum {remote_path}", publish=False)
                if remote_md5 == local_md5:
                    return
        self.put(local_path, "/tmp")
        self.ensure_folder(os.path.dirname(remote_path))
        self._root_run(
            f"mv /tmp/{os.path.basename(local_path)} {remote_path}", hide=True
        )

    def put_content(
        self,
        content: str,
        remote_path: str,
        owner: str = None,
        mode: str = None,
    ) -> None:
        # TODO: not working for win
        self.ensure_folder(os.path.dirname(remote_path))

        temp_path = self.mktemp()
        with self.sftp() as sftp:
            with sftp.file(temp_path, "w") as temp_file:
                temp_file.write(content)

        self._root_run(f"mv {temp_path} {remote_path}", hide=True)
        if owner:
            self._root_run(f"chown {owner} {remote_path}", hide=True)
        if mode:
            self._root_run(f"chmod {mode} {remote_path}", hide=True)


@contextmanager
def connect(server_id: int, **kwargs) -> ContextManager[AuroraConnection]:
    with db_session() as db:
        server = get_server(db, server_id)

    if not server:
        raise AuroraException(f"Server with id {server_id} does not exist")
    try:
        connect_kwargs = {}
        if server.ssh_password:
            connect_kwargs["password"] = server.ssh_password
        if server.key_file:
            connect_kwargs["key_filename"] = server.key_file.storage_path
        if (
            not server.ssh_password
            and not server.key_file
            and pathlib.Path("/app/ansible/env/ssh_key").is_file()
        ):
            connect_kwargs["key_filename"] = "/app/ansible/env/ssh_key"
            # connect_kwargs["key_filename"] = server.key_file.storage_path

        connection_config = {}
        if server.sudo_password:
            connection_config["sudo"] = {"password": server.sudo_password}

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
        yield conn
        conn.close()
    except GroupException as e:
        logger.error(traceback.format_exc())
        raise AuroraException(f"Failed to connect to host: {e}")
    except socket.timeout:
        logger.error(traceback.format_exc())
        raise AuroraException("Connection timed out")
    except Exception as e:
        logger.error(traceback.format_exc())
        raise AuroraException(f"Failed to connect to host: {e}")
