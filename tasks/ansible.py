import json
import ansible_runner
from uuid import uuid4

from . import celery_app
from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule


@celery_app.task()
def ansible_hosts_runner():
    servers = (
        SessionLocal().query(Server).filter(Server.is_active == True).all()
    )

    with open("ansible/inventory/hosts", 'w+') as f:
        f.write("### START AUTO GENERATION ###\n")
        for server in servers:
            f.write(
                f"{server.ansible_name}\tansible_host={server.ansible_host}\tansible_port={server.ansible_port}\tansible_user={server.ansible_user}\n"
            )
        f.write("### END AUTO GENERATION ###")
