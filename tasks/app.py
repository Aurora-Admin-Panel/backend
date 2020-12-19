import json
import typing as t
import ansible_runner
from uuid import uuid4

from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule
from app.db.crud.server import get_server
from app.db.crud.port import get_port

from tasks import celery_app
from tasks.utils.runner import run_async
from tasks.utils.handlers import iptables_finished_handler, status_handler


@celery_app.task()
def app_runner(
    port_id: int,
    server_id: int,
    port_num: int,
    app_name: str,
    app_command: str = None,
    app_config: t.Dict = None,
    app_version_arg: str = '-v',
    app_download_role_name: str = "app_download",
    app_sync_role_name: str = "app_sync",
    app_get_role_name: str = "app_get",
    remote_ip: str = 'ANYWHERE',
    update_status: bool = False,
):
    server = get_server(SessionLocal(), server_id)
    extravars = {
        "host": server.ansible_name,
        "local_port": port_num,
        "remote_ip": remote_ip,
        "app_name": app_name,
        "app_command": app_command,
        "app_version_arg": app_version_arg,
        "app_download_role_name": f"{app_name}_download",
        "app_sync_role_name": app_sync_role_name,
        "app_get_role_name": app_get_role_name,
        "update_status": update_status,
        "update_app": update_status and not server.config.get(app_name),
    }
    if app_config is not None:
        with open(f"ansible/project/roles/app/files/{app_name}-{port_id}.json", "w") as f:
            f.write(json.dumps(app_config, indent=4))
        extravars["app_config"] = f"{app_name}-{port_id}.json"

    r = run_async(
        server=server,
        playbook=f"app.yml",
        extravars=extravars,
        status_handler=lambda s, **k: status_handler(port_id, s, update_status),
        finished_callback=iptables_finished_handler(server, port_id, True)
        if update_status
        else lambda r: None,
    )
    return r[1].config.artifact_dir
