import json
import typing as t
from sqlalchemy import and_, or_
from urllib.parse import urlencode, urlparse

from app.utils.dns import dns_query
from app.utils.ip import is_ip
from app.db.models.port import Port
from app.db.models.server import Server
from app.db.models.port_forward import MethodEnum, PortForwardRule


def generate_gost_config(rule: PortForwardRule) -> t.Dict:
    if rule.method != MethodEnum.GOST:
        return {}
    return {
        "Retries": rule.config.get("Retries", 0),
        "ServeNodes": [
            # TODO: This is not bug free
            node.replace(f":{rule.port.external_num}", f":{rule.port.num}", 1)
            if rule.port.external_num
            else node
            for node in rule.config.get("ServeNodes", [f":{rule.port.num}"])
        ],
        "ChainNodes": rule.config.get("ChainNodes", []),
    }


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
