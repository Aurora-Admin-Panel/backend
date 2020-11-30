import json
import typing as t
import ansible_runner
from uuid import uuid4

from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.crud.server import get_server
from app.db.models.port_forward import PortForwardRule

from . import celery_app
from .utils import prepare_priv_dir_dict


@celery_app.task()
def clean_runner(server: t.Dict):
    priv_data_dir = prepare_priv_dir_dict(server)

    t = ansible_runner.run_async(
        private_data_dir=priv_data_dir,
        project_dir="ansible/project",
        playbook="clean.yml",
        extravars={"host": server.get('ansible_name')},
    )
    return t[1].config.artifact_dir
