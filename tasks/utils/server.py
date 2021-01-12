import os
import typing as t
from shutil import copytree

from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule


def prepare_priv_dir_dict(server: t.Dict) -> str:
    priv_dir = f"ansible/priv_data_dirs/{server.get('id', 0)}"
    os.makedirs(priv_dir, exist_ok=True)
    copytree("ansible/inventory", f"{priv_dir}/inventory", dirs_exist_ok=True)
    copytree("ansible/env", f"{priv_dir}/env", dirs_exist_ok=True)
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