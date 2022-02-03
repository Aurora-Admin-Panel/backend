import typing as t
from sqlalchemy.orm import Session

from app.db.models.port import Port
from app.db.models.port_forward import MethodEnum, PortForwardRule

from app.db.models.port_forward import MethodEnum
from tasks.functions.base import AppConfig


class HaproxyConfig(AppConfig):
    method = MethodEnum.HAPROXY

    def __init__(self):
        super().__init__()

        self.app_name = "haproxy"
        self.app_version_arg = "-v"
        self.app_download_role_name = "void"
        self.app_sync_role_name = "haproxy_install"

        self.traffic_meter = True
        self.update_status = True

    def apply(self, db: Session, port: Port):
        self.local_port = port.num

        config = HaproxyConfig.generate_config(port.forward_rule)
        with open(
            f"ansible/project/roles/app/files/haproxy-{port.id}", "w"
        ) as f:
            f.write(config)
        self.app_command = (
            f"/usr/sbin/haproxy -f /usr/local/etc/aurora/{port.num}"
        )
        self.app_config = f"haproxy-{port.id}"

        self.update_app = not port.server.config.get("haproxy")
        self.applied = True
        return self

    @staticmethod
    def generate_config(rule: PortForwardRule) -> t.Dict:
        return f"""
global
    ulimit-n 51200
defaults
    log global
    retries 1
    option redispatch
    mode {rule.config.get("mode", "tcp")}
    option dontlognull
        timeout connect 5000
        timeout client 95000
        timeout server 95000

frontend {rule.port.num}-in
    bind *:{rule.port.num}
    mode {rule.config.get("mode", "tcp")}
    default_backend {rule.port.num}-out

backend {rule.port.num}-out
    mode {rule.config.get("mode", "tcp")}
    balance {rule.config.get("balance_mode", "roundrobin")}
""" + "\n".join(
            [
                f"    server server{idx} "
                f"{val} check inter 10000 "
                f"maxconn {rule.config.get('maxconn', 20480)} "
                f"{rule.config.get('send_proxy', '')}"
                for idx, val in enumerate(rule.config.get("backend_nodes", []))
            ]
        )

    @property
    def playbook(self):
        return "app.yml"
