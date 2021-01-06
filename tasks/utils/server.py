import re
import os
import hashlib
import typing as t
from datetime import datetime
from collections import defaultdict
from distutils.dir_util import copy_tree
from sqlalchemy.orm import joinedload, Session

from app.utils.tasks import trigger_forward_rule, trigger_tc
from app.utils.size import get_readable_size
from app.db.constants import LimitActionEnum
from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule
from app.db.crud.port import get_port_with_num
from app.db.crud.port_forward import delete_forward_rule, get_forward_rule
from app.db.crud.port_usage import create_port_usage, edit_port_usage
from app.db.crud.server import get_server, get_servers, get_server_users
from app.db.schemas.port_usage import PortUsageCreate, PortUsageEdit
from app.db.schemas.port_forward import PortForwardRuleOut
from app.db.schemas.server import ServerEdit


def prepare_priv_dir_dict(server: t.Dict) -> str:
    priv_dir = f"ansible/priv_data_dirs/{server.get('id', 0)}"
    os.makedirs(priv_dir, exist_ok=True)
    copy_tree("ansible/inventory", f"{priv_dir}/inventory")
    copy_tree("ansible/env", f"{priv_dir}/env")
    passwords = {}
    cmdline = ""
    if server.get("ssh_password") or server.get("sudo_password"):
        if server.get("ssh_password"):
            passwords["^SSH [pP]assword"] = server.get("ssh_password")
            cmdline += " --ask-pass"
        if server.get("sudo_password"):
            passwords["^BECOME [pP]assword"] = server.get("sudo_password")
            cmdline += " -K"
    if not server.get("sudo_password"):
        with open(f"{priv_dir}/env/envvars", "a+") as f:
            f.write("ANSIBLE_PIPELINING: True\n")
    if passwords:
        with open(f"{priv_dir}/env/passwords", "w+") as f:
            f.write("---\n")
            for key, val in passwords.items():
                f.write(f'"{key}": "{val}"\n')
    if cmdline:
        with open(f"{priv_dir}/env/cmdline", "w+") as f:
            f.write(cmdline)
    return priv_dir


def prepare_priv_dir(server: Server) -> str:
    return prepare_priv_dir_dict(server.__dict__)



def iptables_restore_service_enabled(config: t.Dict) -> bool:
    status = config.get('services',{}).get('iptables-restore', {})
    if status.get('status') == 'enabled':
        return True
    return False