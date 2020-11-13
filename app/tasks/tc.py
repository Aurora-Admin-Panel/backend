import json
import ansible_runner

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
def tc_runner(port_id: int):
    port = SessionLocal().query(Port).filter(Port.id == port_id).first()
    if not port:
        print(f"Port not found, id: {port_id}")
        return
    args = ""
    if port.config.get("egress_limit"):
        args += f' -e={port.config.get("egress_limit")}kbit'
    if port.config.get("ingress_limit"):
        args += f' -i={port.config.get("ingress_limit")}kbit'
    args += f' {port.num}'

    t = ansible_runner.run_async(
        private_data_dir="ansible",
        artifact_dir=f"ansible/artifacts/tc/{port_id}",
        playbook="tc.yml",
        extravars={"host": port.server.ansible_name, "tc_args": args},
        finished_callback=finished_handler
    )
    return t[1].config.artifact_dir
