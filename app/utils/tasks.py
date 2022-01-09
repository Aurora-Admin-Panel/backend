from fastapi.encoders import jsonable_encoder

from tasks import celery_app
from app.db.models.port import Port
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule, MethodEnum
from app.db.schemas.server import ServerEdit

from tasks.app import rule_runner


def send_iptables(rule: PortForwardRule):
    kwargs = {
        "port_id": rule.port.id,
        "server_id": rule.port.server.id,
        "local_port": rule.port.num,
        "update_status": True,
        "remote_address": rule.config.get("remote_address"),
        "remote_port": rule.config.get("remote_port"),
        "forward_type": rule.config.get("type", "ALL").upper()
    }
    print(f"Sending iptables_runner task, kwargs: {kwargs}")
    celery_app.send_task("tasks.iptables.iptables_runner", kwargs=kwargs)


def trigger_forward_rule(rule: PortForwardRule):
    print(f"Received forward rule: {jsonable_encoder(rule)}")

    if rule.method in (
        MethodEnum.BROOK,
        MethodEnum.CADDY,
        MethodEnum.EHCO,
        MethodEnum.GOST,
        MethodEnum.NODE_EXPORTER,
        MethodEnum.IPERF,
        MethodEnum.SHADOWSOCKS,
        MethodEnum.SOCAT,
        MethodEnum.TINY_PORT_MAPPER,
        MethodEnum.V2RAY,
        MethodEnum.WSTUNNEL,
        MethodEnum.REALM,
    ):
        rule_runner.delay(rule_id=rule.id)
    elif rule.method == MethodEnum.IPTABLES:
        send_iptables(rule)


def trigger_tc(port: Port):
    kwargs = {
        "server_id": port.server.id,
        "port_num": port.num,
        "egress_limit": port.config.get("egress_limit"),
        "ingress_limit": port.config.get("ingress_limit"),
    }
    print(f"Sending tc_runner task, kwargs: {kwargs}")
    celery_app.send_task("tasks.tc.tc_runner", kwargs=kwargs)


def remove_tc(server_id: int, port_num: int):
    kwargs = {
        "server_id": server_id,
        "port_num": port_num,
    }
    print(f"Sending tc_runner task, kwargs: {kwargs}")
    celery_app.send_task("tasks.tc.tc_runner", kwargs=kwargs)


def trigger_ansible_hosts():
    print("Sending ansible_hosts_runner task")
    celery_app.send_task("tasks.ansible.ansible_hosts_runner")


def trigger_iptables_reset(port: Port):
    kwargs = {"server_id": port.server.id, "port_num": port.num}
    print("Sending iptables.iptables_reset_runner task")
    celery_app.send_task("tasks.iptables.iptables_reset_runner", kwargs=kwargs)


def trigger_server_init(server_id: int, init: bool = False, **kwargs):
    kwargs["server_id"] = server_id
    kwargs["sync_scripts"] = init
    kwargs["init_iptables"] = init
    print("Sending server.server_runner task")
    celery_app.send_task("tasks.server.server_runner", kwargs=kwargs)


def trigger_server_connect(server_id: int, **kwargs):
    kwargs["server_id"] = server_id
    print("Sending server.connect_runner task")
    celery_app.send_task("tasks.server.connect_runner", kwargs=kwargs)


def trigger_server_clean(server: Server):
    print(f"Sending clean.clean_runner task")
    celery_app.send_task(
        "tasks.clean.clean_runner",
        kwargs={"server": ServerEdit(**server.__dict__).dict()},
    )


def trigger_port_clean(server: Server, port: Port, update_traffic: bool = True):
    print(f"Sending clean.clean_port_runner task")
    celery_app.send_task(
        "tasks.clean.clean_port_runner",
        kwargs={"server_id": server.id, "port_num": port.num, "update_traffic": update_traffic},
    )
