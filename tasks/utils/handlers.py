import re
import os
import hashlib
import typing as t
from datetime import datetime
from collections import defaultdict
from distutils.dir_util import copy_tree
from sqlalchemy.orm import joinedload, Session

from app.db.session import SessionLocal, get_db
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule
from app.db.crud.port_forward import delete_forward_rule, get_forward_rule
from app.db.crud.server import get_server, get_servers, get_server_users
from tasks.utils.usage import update_traffic


def update_facts(server_id: int, facts: t.Dict, md5: str = None):
    db = next(get_db())
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
    if "services" in facts:
        db_server.config["services"] = facts.get("services")
    # TODO: Add disable feature
    if "caddy" in facts:
        db_server.config["caddy"] = facts.get("caddy")
    if "iptables" in facts:
        db_server.config["iptables"] = facts.get("iptables")
    if "gost" in facts:
        db_server.config["gost"] = facts.get("gost")
    if "v2ray" in facts:
        db_server.config["v2ray"] = facts.get("v2ray")
    if "brook" in facts:
        db_server.config["brook"] = facts.get("brook")
    if "iperf" in facts:
        db_server.config["iperf"] = facts.get("iperf")
    if "socat" in facts:
        db_server.config["socat"] = facts.get("socat")
    if "ehco" in facts:
        db_server.config["ehco"] = facts.get("ehco")
    if "wstunnel" in facts:
        db_server.config["wstunnel"] = facts.get("wstunnel")
    if "shadowsocks" in facts:
        db_server.config["shadowsocks"] = facts.get("shadowsocks")
    if "node_exporter" in facts:
        db_server.config["node_exporter"] = facts.get("node_exporter")
    if "tiny_port_mapper" in facts:
        db_server.config["tiny_port_mapper"] = facts.get("tiny_port_mapper")
    if md5 is not None:
        db_server.config["init"] = md5
    db.add(db_server)
    db.commit()


def update_rule_error(server_id: int, port_id: int, facts: t.Dict):
    db = SessionLocal()
    db_rule = get_forward_rule(db, server_id, port_id)
    db_rule.config["error"] = "\n".join(
        [facts.get('error', "")] +
        [
            re.search(r"\w+\[[0-9]+\]: (.*)$", line).group(1)
            for line in facts.get('systemd_error', '').split("\n")
            if re.search(r"\w+\[[0-9]+\]: (.*)$", line)
        ]
    ).strip()
    db.add(db_rule)
    db.commit()


def iptables_finished_handler(server: Server, port_id: int = None, accumulate: bool = False):
    def wrapper(runner):
        facts = runner.get_fact_cache(server.ansible_name)
        if facts:
            if facts.get("traffic", ""):
                update_traffic(server, facts.get("traffic", ""), accumulate=accumulate)
            if port_id is not None and (facts.get("error") or facts.get('systemd_error')):
                update_rule_error(server.id, port_id, facts)
            update_facts(server.id, facts)
    return wrapper


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
        if status_data.get("runner_ident"):
            rule.config['runner'] = status_data.get("runner_ident")
        rule.status = status_data.get("status", None)
        db.add(rule)
        db.commit()
    return status_data


def server_facts_event_handler(server: Server):
    def wrapper(event):
        if (
            "event_data" in event
            and event["event_data"].get("task") == "Gathering Facts"
            and not event.get("event", "").endswith("start")
        ):
            res = event["event_data"].get("res", {})
            update_facts(
                server.id,
                res.get("ansible_facts") if "ansible_facts" in res else res,
            )
    return wrapper


def rule_event_handler(server: Server):
    def wrapper(event):
        pass
        # if event.get('event', '').endswith('failed'):
            # print(event.get('stdout'))
    return wrapper