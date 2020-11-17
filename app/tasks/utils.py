import os
import typing as t
from uuid import uuid4
from distutils.dir_util import copy_tree
from sqlalchemy.orm import joinedload

from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule


def prepare_priv_dir(server: Server) -> str:
    priv_dir = f"ansible/priv_data_dirs/{server.id}/{uuid4()}"
    os.makedirs(priv_dir)
    copy_tree("ansible/inventory", f"{priv_dir}/inventory")
    copy_tree("ansible/env", f"{priv_dir}/env")
    passwords = {}
    cmdline = ""
    if server.ssh_password or server.sudo_password:
        if server.ssh_password:
            passwords["^SSH [pP]assword"] = server.ssh_password
            cmdline += " --ask-pass"
        if server.sudo_password:
            passwords["^BECOME [pP]assword"] = server.sudo_password
            cmdline += " -K"
    if passwords:
        with open(f"{priv_dir}/env/passwords", "w+") as f:
            f.write("---\n")
            for key, val in passwords.items():
                f.write(f'"{key}": "{val}"\n')
    if cmdline:
        with open(f"{priv_dir}/env/cmdline", "w+") as f:
            f.write(cmdline)
    return priv_dir
