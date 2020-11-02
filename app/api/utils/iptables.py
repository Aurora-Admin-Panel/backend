import typing as t

from app.tasks import celery_app
from app.db.schemas.port_forward import PortForwardRuleOut
from app.db.models.port_forward import TypeEnum, MethodEnum, PortForwardRule


def trigger_forward_rule(
    rule: PortForwardRule,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    if (new and new.method == MethodEnum.IPTABLES) or (
        old and old.method == MethodEnum.IPTABLES
    ):
        send_iptables_forward_rule(
            rule.id,
            rule.port.server.ansible_host
            if rule.port.server.ansible_host is not None
            else rule.port.server.address,
            rule.port.internal_num
            if rule.port.internal_num is not None and rule.port.internal_num > 0
            else rule.port.num,
            old,
            new,
        )


def send_iptables_forward_rule(
    rule_id: int,
    host: str,
    local_port: int,
    old: PortForwardRuleOut,
    new: PortForwardRuleOut,
):
    kwargs = {
        "rule_id": rule_id,
        "host": host,
        "local_port": local_port,
    }
    protocols = []
    if new and new.method == MethodEnum.IPTABLES:
        kwargs["update_status"] = True
        kwargs["remote_ip"] = new.config.get('remote_ip')
        kwargs["remote_port"] = new.config.get('remote_port')
        forward_type = new.config.get("type", "ALL").upper()
        if forward_type == "ALL" or forward_type == "TCP":
            protocols.append("tcp")
        if forward_type == "ALL" or forward_type == "UDP":
            protocols.append("udp")
    kwargs["protocols"] = str(protocols)

    print(f"Sending iptables_runner task, kwargs: {kwargs}")
    celery_app.send_task(
        "app.tasks.iptables.iptables_runner", kwargs=kwargs
    )
