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


def update_usage(
    db: Session,
    prev_ports: t.Dict,
    db_ports: t.Dict,
    server_id: int,
    port_num: int,
    usage: t.Dict,
    accumulate: bool = False,
):
    if port_num not in db_ports:
        db_port = get_port_with_num(db, server_id, port_num)
        if not db_port:
            print(f"Port not found, num: {port_num}, server_id: {server_id}")
            return
        if not db_port.usage:
            print(
                f"No usage found, creating usage for port id: {db_port.id} {db_port.num}"
            )
            create_port_usage(
                db, db_port.id, PortUsageCreate(port_id=db_port.id)
            )
            db.refresh(db_port)
        db_ports[port_num] = db_port

    port_usage = PortUsageEdit(port_id=db_ports[port_num].id)
    if (
        port_num not in prev_ports
        or not prev_ports[port_num].usage
        or prev_ports[port_num].usage.download_checkpoint
        == db_ports[port_num].usage.download_checkpoint
    ):
        download_usage = (
            usage.get("download", 0)
            + db_ports[port_num].usage.download_accumulate
        )
        port_usage.download = download_usage
        if accumulate:
            port_usage.download_accumulate = download_usage
    if (
        port_num not in prev_ports
        or not prev_ports[port_num].usage
        or prev_ports[port_num].usage.upload_checkpoint
        == db_ports[port_num].usage.upload_checkpoint
    ):
        upload_usage = (
            usage.get("upload", 0) + db_ports[port_num].usage.upload_accumulate
        )
        port_usage.upload = upload_usage
        if accumulate:
            port_usage.upload_accumulate = upload_usage

    edit_port_usage(db, db_ports[port_num].id, port_usage)
    db.refresh(db_ports[port_num])


def apply_port_limits(db: Session, port: Port, action: LimitActionEnum) -> None:
    action_to_speed = {
        LimitActionEnum.SPEED_LIMIT_10K: 10,
        LimitActionEnum.SPEED_LIMIT_100K: 100,
        LimitActionEnum.SPEED_LIMIT_1M: 1000,
        LimitActionEnum.SPEED_LIMIT_10M: 10000,
        LimitActionEnum.SPEED_LIMIT_30M: 30000,
        LimitActionEnum.SPEED_LIMIT_100M: 100000,
        LimitActionEnum.SPEED_LIMIT_1G: 1000000,
    }
    if action == LimitActionEnum.NO_ACTION:
        return
    elif action == LimitActionEnum.DELETE_RULE:
        if not port.forward_rule:
            return
        forward_urle, _ = delete_forward_rule(db, port.server_id, port.id)
        trigger_forward_rule(forward_urle, port, old=forward_urle)
    elif action in action_to_speed:
        db.refresh(port)
        if (
            port.config["egress_limit"] != action_to_speed[action]
            or port.config["ingress_limit"] != action_to_speed[action]
        ):
            port.config["egress_limit"] = action_to_speed[action]
            port.config["ingress_limit"] = action_to_speed[action]
            db.add(port)
            db.commit()
            trigger_tc(port)
    else:
        print(f"No action found {action} for port (id: {port.id})")


def check_limits(config: t.Dict, usage: int) -> LimitActionEnum:
    if config.get(
        "valid_until"
    ) and datetime.utcnow() >= datetime.utcfromtimestamp(
        config.get("valid_until") / 1000
    ):
        return LimitActionEnum(config.get("due_action", 0))
    elif config.get("quota") and usage >= config.get("quota"):
        return LimitActionEnum(config.get("quota_action", 0))
    return None


def check_port_limits(db: Session, port: Port) -> None:
    action = check_limits(port.config, port.usage.download + port.usage.upload)
    if action is not None:
        apply_port_limits(db, port, action)


def check_server_user_limit(
    db: Session, server_id: int, server_users_usage: t.DefaultDict
):
    server_users = get_server_users(db, server_id)
    if not server_users:
        return
    for server_user in server_users:
        server_user.download = server_users_usage[server_user.user_id][
            "download"
        ]
        server_user.upload = server_users_usage[server_user.user_id]["upload"]
        db.add(server_user)
        db.commit()
        db.refresh(server_user)
        action = check_limits(
            server_user.config, server_user.download + server_user.upload
        )
        if action is not None:
            print(f"ServerUser reached limit, apply action {action}")
            for port in server_user.server.ports:
                if server_user.user_id in [
                    u.user_id for u in port.allowed_users
                ]:
                    apply_port_limits(db, port, action)


def iptables_finished_handler(server: Server, accumulate: bool = False):
    def wrapper(runner):
        facts = runner.get_fact_cache(server.ansible_name)
        if facts:
            update_facts(server.id, facts)
        db = SessionLocal()
        pattern = re.compile(r"\/\* (UPLOAD|DOWNLOAD)(?:\-UDP)? ([0-9]+)->")
        prev_ports = {port.num: port for port in server.ports}
        db_ports = {}
        traffics = defaultdict(lambda: {"download": 0, "upload": 0})
        for line in (
            runner.get_fact_cache(server.ansible_name)
            .get("traffic", "")
            .split("\n")
        ):
            match = pattern.search(line)
            if (
                match
                and len(match.groups()) > 1
                and match.groups()[1].isdigit()
            ):
                port_num = int(match.groups()[1])
                traffics[port_num][match.groups()[0].lower()] += int(
                    line.split()[1]
                )
        # print(f"{server.name}: {list(traffics.items())}")
        for port_num, usage in traffics.items():
            update_usage(
                db, prev_ports, db_ports, server.id, port_num, usage, accumulate
            )
        server_users_usage = defaultdict(lambda: {"download": 0, "upload": 0})
        for port in get_server(db, server.id).ports:
            if port.usage:
                check_port_limits(db, port)
                for port_user in port.allowed_users:
                    server_users_usage[port_user.user_id][
                        "download"
                    ] += port.usage.download
                    server_users_usage[port_user.user_id][
                        "upload"
                    ] += port.usage.upload
        check_server_user_limit(db, server.id, server_users_usage)

    return wrapper


def update_facts(server_id: int, facts: t.Dict, md5: str = None):
    db = SessionLocal()
    db_server = get_server(db, server_id)
    if facts.get("ansible_os_family"):
        db_server.config["system"] = {
            "os_family": facts.get("ansible_os_family"),
            "architecture": facts.get("ansible_architecture"),
            "distribution": facts.get("ansible_distribution"),
            "distribution_version": facts.get("ansible_distribution_version"),
            "distribution_release": facts.get("ansible_distribution_release"),
        }
    elif facts.get("msg"):
        db_server.config["system"] = {"msg": facts.get("msg")}
    # TODO: Add disable feature
    if "iptables" in facts:
        db_server.config["iptables"] = facts.get("iptables")
    if "gost" in facts:
        db_server.config["gost"] = facts.get("gost")
    if "v2ray" in facts:
        db_server.config["v2ray"] = facts.get("v2ray")
    if md5 is not None:
        db_server.config["init"] = md5
    db.add(db_server)
    db.commit()


def update_rule_error(server_id: int, port_id: int, error: str):
    db = SessionLocal()
    db_rule = get_forward_rule(db, server_id, port_id)
    db_rule.config["error"] = "\n".join(
        [
            re.search(r"\w+@[0-9]+\.service:(.*)$", line).group(1)
            for line in error.split("\n")
            if re.search(r"\w+@[0-9]+\.service:(.*)$", line)
        ]
    )
    db.add(db_rule)
    db.commit()


def status_handler(port_id: int, status_data: dict, update_status: bool):
    if not update_status:
        return status_data

    db = SessionLocal()
    rule = (
        db.query(PortForwardRule)
        .filter(PortForwardRule.port_id == port_id)
        .first()
    )
    if rule:
        if (
            status_data.get("status", None) == "starting"
            and rule.status == "running"
        ):
            return status_data
        rule.status = status_data.get("status", None)
        db.add(rule)
        db.commit()
    return status_data


def get_md5_for_file(path: str) -> str:
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()