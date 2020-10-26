import typing as t

from app.tasks import celery_app
from app.db.schemas.port_forward import PortForwardRuleOut
from app.db.models.port_forward import TypeEnum, MethodEnum, PortForwardRule


def trigger_forward_rule(
    rule: PortForwardRule,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    if new and new.method == MethodEnum.IPTABLES:
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
    protocols = []
    if new.type == TypeEnum.TCP or new.type == TypeEnum.ALL:
        protocols.append('tcp')
    if new.type == TypeEnum.UDP or new.type == TypeEnum.ALL:
        protocols.append('udp')

    kwargs = {
        "rule_id": rule_id,
        "host": host,
        "local_port": local_port,
        "remote_ip": new.remote_ip,
        "remote_port": new.remote_port,
        "protocols": str(protocols)
    }
    print(f"Sending forward_rule_runner task, kwargs: {kwargs}")
    celery_app.send_task(
            "app.tasks.iptables.forward_rule_runner", kwargs=kwargs
        )
