import json
import ansible_runner
from uuid import uuid4

from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.crud.server import get_server
from app.db.models.port_forward import PortForwardRule

from . import celery_app
from .utils import prepare_priv_dir


def finished_handler(server: Server):
    def wrapper(runner):
        db = SessionLocal()
        db_server = get_server(db, server.id)
        db_server.config['facts'] = runner.get_fact_cache(server.ansible_name)
        db.add(db_server)
        db.commit()
    return wrapper
        

@celery_app.task()
def connect_runner(
    server_id: int,
):
    server = get_server(SessionLocal(), server_id)
    priv_data_dir = prepare_priv_dir(server)

    t = ansible_runner.run_async(
        private_data_dir=priv_data_dir,
        project_dir="ansible/project",
        playbook="connect.yml",
        extravars={"host": server.ansible_name},
        finished_callback=finished_handler(server),
    )
    return t[1].config.artifact_dir
