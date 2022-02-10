import re
import typing as t

from app.db.session import db_session
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule
from app.db.crud.port_forward import get_forward_rule
from app.db.crud.server import get_server
from tasks.utils.usage import update_traffic


def update_facts(server_id: int, facts: t.Dict, md5: str = None):
    with db_session() as db:
        db_server = get_server(db, server_id)
        if facts.get("ansible_os_family"):
            db_server.config["system"] = {
                "os_family": facts.get("ansible_os_family"),
                "architecture": facts.get("ansible_architecture"),
                "distribution": facts.get("ansible_distribution"),
                "distribution_version": facts.get(
                    "ansible_distribution_version"
                ),
                "distribution_release": facts.get(
                    "ansible_distribution_release"
                ),
            }
        elif facts.get("msg"):
            db_server.config["system"] = {"msg": facts.get("msg")}
        if "services" in facts:
            db_server.config["services"] = facts.get("services")
        # TODO: Add disable feature
        for func in [
            "brook",
            "caddy",
            "ehco",
            "gost",
            "iperf",
            "iptables",
            "node_exporter",
            "shadowsocks",
            "socat",
            "tiny_port_mapper",
            "v2ray",
            "wstunnel",
            "realm",
            "haproxy",
        ]:
            if func in facts:
                db_server.config[func] = facts.get(func)
        if md5 is not None:
            db_server.config["init"] = md5
        db.add(db_server)
        db.commit()


def update_rule_error(server_id: int, port_id: int, facts: t.Dict):
    with db_session() as db:
        db_rule = get_forward_rule(db, server_id, port_id)
        db_rule.config["error"] = "\n".join(
            [facts.get("error", "")]
            + [
                re.search(r"\w+\[[0-9]+\]: (.*)$", line).group(1)
                for line in facts.get("systemd_error", "").split("\n")
                if re.search(r"\w+\[[0-9]+\]: (.*)$", line)
            ]
        ).strip()
        db.add(db_rule)
        db.commit()


def iptables_finished_handler(
    server_id: int,
    port_id: int = None,
    accumulate: bool = False,
    update_traffic_bool: bool = True,
):
    def wrapper(runner):
        with db_session() as db:
            server = get_server(db, server_id)
        facts = runner.get_fact_cache(server.ansible_name)
        if facts:
            if facts.get("traffic", "") and update_traffic_bool:
                update_traffic(
                    server, facts.get("traffic", ""), accumulate=accumulate
                )
            if port_id is not None and (
                facts.get("error") or facts.get("systemd_error")
            ):
                update_rule_error(server.id, port_id, facts)
            update_facts(server.id, facts)
    return wrapper


def status_handler(port_id: int, status_data: dict, update_status: bool):
    if update_status:
        with db_session() as db:
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
                    rule.config["runner"] = status_data.get("runner_ident")
                rule.status = status_data.get("status", None)
                db.add(rule)
                db.commit()
    return status_data


def server_facts_event_handler(server_id: int):
    def wrapper(event):
        if (
            "event_data" in event
            and event["event_data"].get("task") == "Gathering Facts"
            and not event.get("event", "").endswith("start")
        ):
            res = event["event_data"].get("res", {})
            update_facts(
                server_id,
                res.get("ansible_facts") if "ansible_facts" in res else res,
            )

    return wrapper
