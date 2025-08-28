import os
import typing as t
from typing import Optional
from dataclasses import dataclass
from shutil import copytree

from sqlalchemy.orm import Session
from app.db.models import Server


@dataclass
class ServerFacts:
    mem_total: Optional[int] = None
    swap_total: Optional[int] = None
    root_total: Optional[int] = None
    os_release: Optional[str] = None
    probe_version: Optional[str] = None


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


def update_facts(db: Session, server: Server, facts: ServerFacts):
    facts_match = True
    if facts.mem_total is not None and server.mem_total != facts.mem_total:
        facts_match = False
        server.mem_total = facts.mem_total
    if facts.swap_total is not None and server.swap_total != facts.swap_total:
        facts_match = False
        server.swap_total = facts.swap_total
    if facts.root_total is not None and server.root_total != facts.root_total:
        facts_match = False
        server.root_total = facts.root_total
    if facts.os_release is not None and server.os_release != facts.os_release:
        facts_match = False
        server.os_release = facts.os_release
    if facts.probe_version is not None and server.probe_version != facts.probe_version:
        facts_match = False
        server.probe_version = facts.probe_version
    if not facts_match:
        db.add(server)
