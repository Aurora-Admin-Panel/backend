import asyncio

from fabric import Config
from tasks.utils.packages import PackageState
from tasks.utils.systemd import ServiceRuntimeState, ServiceEnableState
from tasks.utils.connection import AuroraConnection
from tasks.utils.orchestrator import SystemOrchestrator
from tasks.utils.interval import jitter
from tasks.utils.connect import connect

# sudo_watcher = Responder(pattern=r"\[sudo\] password.*:", response="2143wq\n")


def main() -> None:
    with connect(server_id=203) as c:
        # c.sudo("whoami", hide="stderr")
        # print(c.execute("stat -c '%a %U %G' /tmp/test_file.txt"))
        orch = SystemOrchestrator(c)
        res = (
            #     "test_file",
            #     "/tmp/test_file.txt",
            #     # src="/home/lei/workspace/created/aurora/backend/test_async.py",
            #     content="This is a test file.\nOr not?",
            #     owner="lei",
            #     mode="0644",
            # )
            # .ensure_directory(
            #     "test_dir", "/tmp/test2/test_dir", owner="lei", mode="0755", recursive=False
            # )
            orch.system_info().execute()
        )
        print(res)


main()
