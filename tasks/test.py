import time
import redis
from huey.api import Task
from app.core import config

from .config import huey
from tasks.utils.connection import connect


@huey.task(priority=3, context=True)
def test_runner(server_id: int, task: Task):
    try:
        with connect(server_id=server_id, task=task) as c:
            c.run("echo 1")
            c.run("echo 2")
            c.run("echo 3")
            c.run("cat /etc/os-release")
            return {"success": True}
    except Exception as e:
        # TODO: handle exception
        return {"error": str(e)}
