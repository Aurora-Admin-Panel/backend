import os
import time
import pathlib
from pathlib import Path
from decimal import Decimal
from typing import Tuple, Union
from datetime import datetime

import redis
from fabric import Connection, Result

from app.core import config

from tasks.utils.exception import AuroraException
from tasks.utils.helper import q
from tasks.utils.files import get_md5_for_file


class AuroraConnection(Connection):
    def __init__(self, *args, **kwargs):
        self._set(task=kwargs.pop("task", None))
        self._set(
            redis=redis.StrictRedis(host=config.REDIS_HOST, port=config.REDIS_PORT)
        )

        if self.task:
            self.redis.zadd(
                "aurora:task:ids",
                {self.task.id: datetime.utcnow().timestamp()},
            )
        super().__init__(*args, **kwargs)

    def __enter__(self):
        context = super().__enter__()
        self.check_sudo()
        return context

    @property
    def is_root(self):
        return self.user == "root"

    def check_sudo(self):
        if not self.is_root:
            groups = super().run("groups", pty=True, hide=True).stdout.strip()
            if "sudo" not in groups:
                raise AuroraException("User is not in sudo group")

    def _root_run(self, *args, pty: bool = True, **kwargs):
        if self.is_root:
            return super().run(*args, pty=pty, **kwargs)
        else:
            return super().sudo(*args, pty=pty, **kwargs)

    def strip_stdout(self, result: Result) -> str:
        return result.stdout.strip("[sudo] password:").strip()

    def run(self, *args, publish: bool = True, **kwargs) -> str:
        # logger.debug(f"Running {args} on {self.host}")
        result = self._root_run(*args, hide=True, **kwargs)
        # stdout and stderr should already combined because the
        # behavior of pty=True
        stdout = self.strip_stdout(result)
        if publish:
            self.publish(stdout)
        return stdout

    def execute(self, cmd: str, *, pty: bool = True) -> Result:
        return self._root_run(cmd, hide=True, warn=True, pty=pty)

    def _test(self, flag: str, path: Union[str, Path]) -> bool:
        cmd = f"test {flag} {q(str(path))}"
        return self.execute(cmd, pty=False).ok

    # public shortcuts
    def exists(self, path: Union[str, Path]) -> bool:
        return self._test("-e", path)

    def file_exists(self, path: Union[str, Path]) -> bool:
        return self._test("-f", path)

    def directory_exists(self, path: Union[str, Path]) -> bool:
        return self._test("-d", path)

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

    def get_file_md5sum(self, path: str) -> str:
        return self.run(f"md5sum '{path}' | cut -d' ' -f1")

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

    def mktemp(self) -> str:
        return super().run("mktemp", hide=True).stdout.strip()

    def ensure_folder(
        self, path: str | Path, owner: str = None, mode: str = None
    ) -> Result:
        if not self.directory_exists(path):
            self._root_run(f"mkdir -p {path}")

        if owner:
            self._root_run(f"chown {owner} {path}")
        elif owner is None:
            self._root_run(f"chown {self.user}:{self.user} {path}")

        if mode:
            self._root_run(f"chmod {mode} {path}")

    def ensure_file(
        self, local_path: str, remote_path: str, ensure_same: bool = True
    ) -> None:
        if not pathlib.Path(local_path).exists():
            raise AuroraException(f"{local_path} does not exist")

        if self.file_exists(remote_path):
            if ensure_same:
                local_md5 = get_md5_for_file(local_path)
                remote_md5 = self.get_file_md5sum(remote_path)
                if remote_md5 == local_md5:
                    return
        self.put(local_path, "/tmp")
        self.ensure_folder(os.path.dirname(remote_path))
        self._root_run(
            f"mv /tmp/{os.path.basename(local_path)} {remote_path}", hide=True
        )

    def ensure_content(
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
