import json
import ansible_runner
from uuid import uuid4

from . import celery_app
from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule

def finished_handler(runner):
    for event in runner.events:
        if event.get('event_data', {}).get('task') == 'Exec tc script' and 'res' in event.get('event_data', {}):
            print(event['event_data']['res']['stdout_lines'])


@celery_app.task()
def tc_runner(
    host: str,
    port_id: int,
    port_num: int,
    egress_limit: int = None,
    ingress_limit: int = None
):
    args = ""
    if egress_limit:
        args += f' -e={egress_limit}kbit'
    if ingress_limit:
        args += f' -i={ingress_limit}kbit'
    args += f' {port_num}'

    t = ansible_runner.run_async(
        private_data_dir="ansible",
        artifact_dir=f"ansible/artifacts/{port_id}/tc/{uuid4()}",
        playbook="tc.yml",
        extravars={"host": host, "tc_args": args},
        finished_callback=finished_handler
    )
    return t[1].config.artifact_dir
