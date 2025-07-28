import asyncio

from invoke import Responder
from fabric import Config
from tasks.utils.connection import AuroraConnection
from tasks.utils.orchestrator import SystemOrchestrator

sudo_watcher = Responder(pattern=r"\[sudo\] password.*:", response="2143wq\n")


def main() -> None:
    connection_config = {}
    connection_config["sudo"] = {"password": "2143wq"}
    c = AuroraConnection(
        host="hk2.leishi.io",
        config=Config(overrides=connection_config),
        # watchers=[sudo_watcher],
    )
    # c.sudo("whoami", hide="stderr")
    # print(c.execute("stat -c '%a %U %G' /tmp/test_file.txt"))
    orch = SystemOrchestrator(c)
    res = (
        orch.ensure_file(
            "test_file",
            "/tmp/test_file.txt",
            # src="/home/lei/workspace/created/aurora/backend/test_async.py",
            content="This is a test file.\nOr not?",
            owner="lei",
            mode="0644",
        )
        .ensure_directory(
            "test_dir",
            "/tmp/test_dir",
            owner="lei",
            mode="0755",
        )
        # .ensure_package(
        #     "git",
        #     state="present",
        #     version="2.25.1",
        # )
        .execute()
    )
    print(res)


main()
