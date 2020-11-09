import json
import typing as t
from sqlalchemy import and_, or_
from urllib.parse import urlencode, urlparse

from app.tasks import celery_app
from app.api.utils.dns import dns_query
from app.api.utils.ip import is_ip
from app.db.session import SessionLocal
from app.db.schemas.port_forward import PortForwardRuleOut
from app.db.models.port import Port
from app.db.models.server import Server
from app.db.models.port_forward import MethodEnum, PortForwardRule


def send_gost_rule(
    port_id: int,
    host: str,
    update_status: bool,
    update_gost: bool = False,
):
    kwargs = {
        "port_id": port_id,
        "host": host,
        "update_gost": update_gost,
        "update_status": update_status,
    }
    print(f"Sending gost_runner task, kwargs: {kwargs}")
    celery_app.send_task("app.tasks.gost.gost_runner", kwargs=kwargs)


def generate_gost_config(rule: PortForwardRule) -> t.Dict:
    return {
        "Retries": rule.config.get("Retries", 0),
        "ServeNodes": [
            node.replace(f":{rule.port.external_num}", f":{rule.port.num}", 1)
            if rule.port.external_num
            else node
            for node in rule.config.get("ServeNodes", [f":{rule.port.num}"])
        ],
        "ChainNodes": rule.config.get("ChainNodes", []),
    }


def get_gost_config(port_id: int) -> t.Tuple[int, t.Dict]:
    db = SessionLocal()
    port = db.query(Port).filter(Port.id == port_id).first()
    # Here we will use only the first rule.
    if (
        port
        and port.forward_rule
        and port.forward_rule.method == MethodEnum.GOST
    ):
        return port.num, generate_gost_config(port.forward_rule)
    return port.num, {}


def get_gost_remote_ip(config: t.Dict) -> str:
    if config.get("ChainNodes", []):
        first_chain_node = config["ChainNodes"][0]
        ip_or_address = (
            urlparse(first_chain_node).netloc.split("@")[-1].split(":")[0]
        )
        if not ip_or_address:
            return "127.0.0.1"
        elif is_ip(ip_or_address):
            return ip_or_address
        else:
            return dns_query(ip_or_address)
    elif config.get("ServeNodes", []):
        tcp_nodes = list(
            filter(lambda r: r.startswith("tcp"), config["ServeNodes"])
        )
        if tcp_nodes:
            parsed = urlparse(tcp_nodes[0])
            if parsed.path:
                ip_or_address = parsed.path[1:].split(":")[0]
                if is_ip(ip_or_address):
                    return ip_or_address
                else:
                    return dns_query(ip_or_address)
    return ""
