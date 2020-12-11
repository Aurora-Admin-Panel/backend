import os
import typing as t
import ansible_runner
from uuid import uuid4

from app.db.models.server import Server

from tasks.utils.server import prepare_priv_dir, prepare_priv_dir_dict


def run_async(
    server: t.Union[Server, t.Dict],
    playbook: str,
    extravars: t.Dict = None,
    **kwargs
):
    if extravars is None:
        extravars = {}
    if isinstance(server, dict):
        priv_data_dir = prepare_priv_dir_dict(server)
        extravars["host"] = server["ansible_name"]
    else:
        priv_data_dir = prepare_priv_dir(server)
        extravars["host"] = server.ansible_name
    return ansible_runner.run_async(
        ident=uuid4(),
        private_data_dir=priv_data_dir,
        project_dir="ansible/project",
        playbook=playbook,
        extravars=extravars,
        **kwargs
    )
