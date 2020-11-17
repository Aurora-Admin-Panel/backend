from fastapi.encoders import jsonable_encoder

from app.tasks import celery_app
from app.db.models.port import Port
from app.db.models.port_forward import PortForwardRule, MethodEnum
from app.db.schemas.port_forward import PortForwardRuleOut

from .gost import generate_gost_config, get_gost_remote_ip


def send_iptables(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
    update_gost: bool = False,
):
    kwargs = {
        "port_id": port.id,
        "server_id": port.server.id,
        "local_port": port.num,
    }
    protocols = []
    if new and new.method == MethodEnum.IPTABLES:
        kwargs["update_status"] = True
        kwargs["remote_ip"] = new.config.get("remote_ip")
        kwargs["remote_port"] = new.config.get("remote_port")
        forward_type = new.config.get("type", "ALL").upper()
        if forward_type == "ALL" or forward_type == "TCP":
            protocols.append("tcp")
        if forward_type == "ALL" or forward_type == "UDP":
            protocols.append("udp")
    kwargs["protocols"] = str(protocols)
    print(f"Sending iptables_runner task, kwargs: {kwargs}")
    celery_app.send_task("app.tasks.iptables.iptables_runner", kwargs=kwargs)


def send_gost(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
    update_gost: bool = False,
):
    gost_config = generate_gost_config(rule)
    kwargs = {
        "port_id": port.id,
        "server_id": port.server.id,
        "port_num": port.num,
        "gost_config": gost_config,
        "remote_ip": get_gost_remote_ip(gost_config),
        "update_gost": update_gost,
        "update_status": bool(new and new.method == MethodEnum.GOST),
    }
    print(f"Sending gost_runner task, kwargs: {kwargs}")
    celery_app.send_task("app.tasks.gost.gost_runner", kwargs=kwargs)


def trigger_forward_rule(
    rule: PortForwardRule,
    port: Port,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
    update_gost: bool = False,
):
    print(
        f"Received forward rule:\n"
        + f"old:{jsonable_encoder(old) if old else None}\n"
        + f"new:{jsonable_encoder(new) if new else None}"
    )
    if any(r.method == MethodEnum.IPTABLES for r in (old, new) if r):
        send_iptables(rule, port, old, new, update_gost)

    if any(r.method == MethodEnum.GOST for r in (old, new) if r):
        send_gost(rule, port, old, new, update_gost)


def trigger_tc(port: Port):
    kwargs = {
        "server_id": port.server.id,
        "port_num": port.num,
        "egress_limit": port.config.get("egress_limit"),
        "ingress_limit": port.config.get("ingress_limit"),
    }
    print(f"Sending tc_runner task, kwargs: {kwargs}")
    celery_app.send_task("app.tasks.tc.tc_runner", kwargs=kwargs)

def remove_tc(server_id: int, port_num: int):
    kwargs = {
        "server_id": server_id,
        "port_num": port_num,
    }
    print(f"Sending tc_runner task, kwargs: {kwargs}")
    celery_app.send_task("app.tasks.tc.tc_runner", kwargs=kwargs)

def trigger_ansible_hosts():
    print(f"Sending ansible_hosts_runner task")
    celery_app.send_task("app.tasks.ansible.ansible_hosts_runner")
