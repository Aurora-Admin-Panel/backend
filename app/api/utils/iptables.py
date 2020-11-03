import typing as t

from app.tasks import celery_app
from app.db.schemas.port_forward import PortForwardRuleOut
from app.db.models.port_forward import TypeEnum, MethodEnum, PortForwardRule


def send_iptables_forward_rule(
    port_id: int,
    host: str,
    local_port: int,
    old: PortForwardRuleOut,
    new: PortForwardRuleOut,
):
    kwargs = {
        "port_id": port_id,
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
