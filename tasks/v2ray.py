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

from . import celery_app
from .runner import run_async
from .utils import iptables_finished_handler


@celery_app.task()
def status_handler(port_id: int, status_data: dict, update_status: bool):
    if not update_status:
        return status_data

    db = SessionLocal()
    rule = (
        db.query(PortForwardRule)
        .filter(PortForwardRule.port_id == port_id)
        .first()
    )
    if rule:
        if (
            status_data.get("status", None) == "starting"
            and rule.status == "running"
        ):
            return status_data
        rule.status = status_data.get("status", None)
        db.add(rule)
        db.commit()
    return status_data


@celery_app.task()
def v2ray_runner(
    port_id: int,
    server_id: int,
    port_num: int,
    v2ray_config: t.Dict,
    remote_ip: str = None,
    update_status: bool = False,
):
    server = get_server(SessionLocal(), server_id)
    with open(f"ansible/project/roles/v2ray/files/{port_id}.json", "w") as f:
        f.write(json.dumps(v2ray_config, indent=4))

    extravars = {
        "host": server.ansible_name,
        "port_id": port_id,
        "local_port": port_num,
        "remote_ip": remote_ip,
        "update_status": update_status,
        "update_v2ray": update_status and not server.config.get('v2ray'),
    }
    r = run_async(
        server=server,
        playbook="v2ray.yml",
        extravars=extravars,
        status_handler=lambda s, **k: status_handler(port_id, s, update_status),
        finished_callback=iptables_finished_handler(server, True)
        if update_status
        else lambda r: None,
    )
    return r[1].config.artifact_dir
