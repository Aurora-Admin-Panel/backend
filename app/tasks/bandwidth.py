import os
import ansible_runner
from uuid import uuid4
from distutils.dir_util import copy_tree

from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.crud.server import get_server, get_servers
from app.db.models.port_forward import PortForwardRule

from . import celery_app
from .utils import prepare_priv_dir


def finished_handler(server):
    def wrapper(runner):
        print("#######################")
        # print(os.listdir(f"{runner.config.fact_cache}"))
        print(f"{server.ansible_name}: {runner.get_fact_cache(server.ansible_name)}")
        # print([port.__dict__ for port in server.ports])
        # db_server = SessionLocal().query(Server).filter(Server.id == server.id).first()
        # print([port.__dict__ for port in db_server.ports])
        print("#######################")
    return wrapper


@celery_app.task()
def bandwidth_runner():
    servers = get_servers(SessionLocal())
    for server in servers:
        priv_data_dir = prepare_priv_dir(server)
        ansible_runner.run_async(
            private_data_dir=priv_data_dir,
            project_dir="ansible/project",
            playbook="bandwidth.yml",
            extravars={"host": server.ansible_name},
            finished_callback=finished_handler(server),
        )
