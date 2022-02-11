import json
import typing as t
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from app.db.models.port import Port
from app.db.models.port_forward import MethodEnum, PortForwardRule
from app.utils.ip import is_ip
from app.utils.dns import dns_query

from tasks.functions.base import AppConfig


class GostConfig(AppConfig):
    method = MethodEnum.GOST

    def __init__(self):
        super().__init__()

        self.app_name = "gost"
        self.app_path = "/usr/local/bin/"
        self.app_version_arg = "-V"

        self.app_sync_role_name = "gost_sync"

        self.traffic_meter = True
        self.update_status = True

    def apply(self, db: Session, port: Port):
        self.local_port = port.num

        config = GostConfig.generate_gost_config(port.forward_rule)
        with open(f"ansible/project/roles/app/files/gost-{port.id}", "w") as f:
            f.write(json.dumps(config, indent=2))
        self.app_command = f"/usr/local/bin/gost -C /usr/local/etc/aurora/{port.num}"
        self.app_config = f"gost-{port.id}"
        self.remote_ip = GostConfig.get_gost_remote_ip(config)

        self.update_app = not port.server.config.get("gost")
        self.applied = True
        return self

    @staticmethod
    def generate_gost_config(rule: PortForwardRule) -> t.Dict:
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

    @staticmethod
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
        return "ANYWHERE"

    @property
    def playbook(self):
        return "app.yml"
