import re

import tasks.app
from app.db.session import db_session
from app.db.models.port_forward import MethodEnum
from app.db.crud.port_forward import get_forward_rule_for_server


def correct_running_services(server_id: int, rules: str):
    port_pattern = re.compile(r"aurora@([0-9]+)\.service")
    app_pattern = re.compile(r"ExecStart=/(?:\w+\/)+(\w+)")
    port_rule = {}

    for service in rules.split("\n"):
        port_match = port_pattern.search(service)
        app_match = app_pattern.search(service)
        if port_match and port_match.groups()[0].isdigit() and app_match:
            port_rule[int(port_match.groups()[0])] = app_match.groups()[0]
    print(f"Current rules of server {server_id}: {port_rule}")

    with db_session() as db:
        db_forward_rules = get_forward_rule_for_server(db, server_id)
    for db_forward_rule in db_forward_rules:
        # TODO: check rule's app bin and status
        if (
            not port_rule.get(db_forward_rule.port.num)
            and db_forward_rule.method != MethodEnum.IPTABLES
        ):
            print(
                f"Forward rule of server {db_forward_rule.port.server_id} "
                f"port {db_forward_rule.port.num} not match with db rule, "
                f"recreating rule {db_forward_rule.method} {db_forward_rule.config}"
            )
            tasks.app.rule_runner(rule_id=db_forward_rule.id)
