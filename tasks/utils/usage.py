import re
import typing as t
from datetime import datetime
from collections import defaultdict
from sqlalchemy.orm import Session

from app.db.constants import LimitActionEnum
from app.db.session import db_session
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule
from app.db.crud.port import get_port_with_num, get_port_by_id
from app.db.crud.port_forward import delete_forward_rule, get_forward_rule
from app.db.crud.port_usage import create_port_usage, edit_port_usage
from app.db.crud.server import get_server_with_ports_usage, get_servers, get_server_users
from app.db.schemas.port_usage import PortUsageCreate, PortUsageEdit
from app.db.schemas.port_forward import PortForwardRuleOut
from app.db.schemas.server import ServerEdit

from tasks.port import clean_port_no_update_runner
from tasks.tc import tc_runner


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


def apply_port_limits(db: Session, port: Port, action: LimitActionEnum):
    action_to_speed = {
        LimitActionEnum.SPEED_LIMIT_10K: 10,
        LimitActionEnum.SPEED_LIMIT_100K: 100,
        LimitActionEnum.SPEED_LIMIT_1M: 1000,
        LimitActionEnum.SPEED_LIMIT_10M: 10000,
        LimitActionEnum.SPEED_LIMIT_30M: 30000,
        LimitActionEnum.SPEED_LIMIT_100M: 100000,
        LimitActionEnum.SPEED_LIMIT_1G: 1000000,
    }
    db.refresh(port)
    if action == LimitActionEnum.NO_ACTION:
        return
    elif action == LimitActionEnum.DELETE_RULE:
        if not port.forward_rule:
            return
        delete_forward_rule(db, port.server_id, port.id)
        clean_port_no_update_runner(server_id=port.server.id, port_num=port.num)
    elif action in action_to_speed:
        if (
            port.config["egress_limit"] != action_to_speed[action]
            or port.config["ingress_limit"] != action_to_speed[action]
        ):
            port.config["egress_limit"] = action_to_speed[action]
            port.config["ingress_limit"] = action_to_speed[action]
            db.add(port)
            db.commit()
            tc_runner.apply_async(
                kwargs={
                    "server_id": port.server.id,
                    "port_num": port.num,
                    "egress_limit": port.config.get("egress_limit"),
                    "ingress_limit": port.config.get("ingress_limit"),
                },
                priority=0,
            )
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
    db: Session, server: Server, server_users_usage: t.DefaultDict
):
    for server_user in server.allowed_users:
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


def update_traffic(
    server: Server, traffic: str, accumulate: bool = False
):
    pattern = re.compile(r"\/\* (UPLOAD|DOWNLOAD)(?:\-UDP)? ([0-9]+)->")
    prev_ports = {port.num: port for port in server.ports}
    db_ports = {}
    traffics = defaultdict(lambda: {"download": 0, "upload": 0})

    for line in traffic.split("\n"):
        match = pattern.search(line)
        if match and len(match.groups()) > 1 and match.groups()[1].isdigit():
            port_num = int(match.groups()[1])
            traffics[port_num][match.groups()[0].lower()] += int(
                line.split()[1]
            )
    with db_session() as db:
        for port_num, usage in traffics.items():
            update_usage(
                db, prev_ports, db_ports, server.id, port_num, usage, accumulate
            )
    server_users_usage = defaultdict(lambda: {"download": 0, "upload": 0})
    with db_session() as db:
        server = get_server_with_ports_usage(db, server.id)
        for port in server.ports:
            if port.usage:
                check_port_limits(db, port)
                for port_user in port.allowed_users:
                    server_users_usage[port_user.user_id][
                        "download"
                    ] += port.usage.download
                    server_users_usage[port_user.user_id][
                        "upload"
                    ] += port.usage.upload
        check_server_user_limit(db, server, server_users_usage)
