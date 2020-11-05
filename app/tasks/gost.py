import json
import ansible_runner

from . import celery_app
from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule
from app.api.utils.gost import get_gost_config


@celery_app.task()
def gost_finished_handler(stdout_name: str):
    pass
    # with open(stdout_name, 'r') as f:
    # return f.read()


@celery_app.task()
def gost_status_handler(port_id: int, status_data: dict, update_status: bool):
    if not update_status:
        return status_data

    db = SessionLocal()
    rule = (
        db.query(PortForwardRule).filter(PortForwardRule.port_id == port_id).first()
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
def gost_runner(
    port_id: int,
    host: str,
    update_gost: bool = False,
    update_status: bool = False
):
    port_num, config = get_gost_config(port_id)
    with open(f'ansible/project/roles/gost/files/{port_num}.json', 'w') as f:
        f.write(json.dumps(config, indent=4))

    extra_vars = {
        "host": host,
        "port_id": port_num,
        "update_gost": update_gost
    }
    t = ansible_runner.run_async(
        private_data_dir="ansible",
        artifact_dir=f"ansible/artifacts/gost/{port_id}",
        playbook="gost.yml",
        extravars=extra_vars,
        status_handler=lambda s, **k: gost_status_handler.delay(
            port_id, s, update_status
        ),
        finished_callback=lambda r: gost_finished_handler.delay(
            r.stdout.name
        ),
    )
    return config, t[1].config.artifact_dir
