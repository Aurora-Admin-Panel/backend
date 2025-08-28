import re
import io
import time
import asyncio
import pathlib
from pathlib import Path
from decimal import Decimal
from typing import Tuple, Union
from datetime import datetime, timedelta, timezone

from loguru import logger
import redis
from redis import Redis
from huey.api import Task
from fabric import Connection, Result

from app.core import config, codec
from app.core.redis_keyspace import Keys

from tasks.utils.redis_client import get_redis
from tasks.utils.exception import AuroraException
from tasks.utils.helper import q


class AuroraConnection(Connection):
    task: Task = None
    redis: Redis = None

    def __init__(self, *args, **kwargs):
        self._set(task=kwargs.pop("task", None))
        self._set(redis=get_redis())

        if self.task:
            self.redis.zadd(
                Keys.task_ids(),
                {self.task.id: int(time.time_ns())},
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
        if not self.is_connected:
            self.open()
        if not self.is_root:
            groups = super().run("groups", pty=True, hide=True).stdout.strip()
            if "sudo" not in groups:
                raise AuroraException("User is not in sudo group")

    def _root_run(self, *args, **kwargs):
        if self.is_root:
            return super().run(*args, **kwargs)
        else:
            kwargs.pop("pty", None)
            return super().sudo(*args, pty=True, **kwargs)

    def strip_stdout(self, result: Result) -> str:
        out = result.stdout
        out = re.sub(r"^\[sudo\]\s+password:\s*", "", out, count=1)
        return out.strip()

    def run(self, *args, publish: bool = True, **kwargs) -> str:
        # logger.debug(f"Running {args} on {self.host}")
        result = self._root_run(*args, hide=True, **kwargs)
        # stdout and stderr should already combined because the
        # behavior of pty=True
        stdout = self.strip_stdout(result)
        if publish:
            self.publish(stdout)
        return stdout

    def execute(self, cmd: str) -> Result:
        return self._root_run(cmd, hide=True, warn=True)

    def _test(self, flag: str, path: Union[str, Path]) -> bool:
        cmd = f"test {flag} {q(str(path))}"
        return self.execute(cmd).ok

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
            self.publish(config.PUBSUB_STOPWORD)
        self.redis.close()
        super().close()

    def publish(self, text: str):
        if not self.task:
            return

        now_ns = time.time_ns()
        payload = codec.dumps(
            {
                "text": text,
                "task_id": self.task.id,
                "ts_ns": now_ns,
            }
        )
        pipe = self.redis.pipeline(transaction=False)
        pipe.xadd(
            Keys.task_stream(self.task.id),
            {"payload": payload},
            maxlen=config.PUBSUB_STREAM_MAXLEN,
            approximate=True,
        )
        pipe.zadd(Keys.task_ids(), {self.task.id: now_ns // 1000})
        pipe.expire(
            Keys.task_stream(self.task.id),
            timedelta(days=int(config.TASK_OUTPUT_STORAGE_DAYS)),
        )
        pipe.execute()

    def mktemp(self) -> str:
        return super().run("mktemp", hide=True).stdout.strip()
