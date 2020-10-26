import ansible_runner

from . import celery_app
from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule


@celery_app.task()
def forward_rule_finished_handler(stdout_name: str):
    pass
    # with open(stdout_name, 'r') as f:
    # return f.read()


@celery_app.task()
def forward_rule_status_handler(rule_id: int, status_data: dict):
    db = SessionLocal()
    rule = (
        db.query(PortForwardRule).filter(PortForwardRule.id == rule_id).first()
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
def forward_rule_runner(
    rule_id: int,
    host: str,
    local_port: int,
    remote_ip: str,
    remote_port: int,
    protocols: str,
):
    extra_vars = {
        "hosts": host,
        "local_port": local_port,
        "remote_ip": remote_ip,
        "remote_port": remote_port,
        "protocols": protocols,
    }

    t = ansible_runner.run_async(
        private_data_dir="ansible",
        artifact_dir=f"ansible/{rule_id}",
        playbook="iptables_forward_rule.yml",
        extravars=extra_vars,
        status_handler=lambda s, **k: forward_rule_status_handler.delay(
            rule_id, s
        ),
        finished_callback=lambda r: forward_rule_finished_handler.delay(
            r.stdout.name
        ),
    )
    return t[1].config.artifact_dir
