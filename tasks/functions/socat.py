from sqlalchemy.orm import Session

from app.db.models.port import Port
from app.db.models.port_forward import MethodEnum
from app.utils.ip import is_ipv6
from tasks.functions.base import AppConfig


class SocatConfig(AppConfig):
    method = MethodEnum.SOCAT

    def __init__(self):
        super().__init__()
        self.app_name = "socat"
        self.app_version_arg = "-V"
        self.app_sync_role_name = "socat_install"


    def apply(self, db: Session, port: Port):
        self.local_port = port.num
        self.app_command = self.get_app_command(port)
        self.update_app = not port.server.config.get("socat")
        self.applied = True
        return self

    def get_app_command(self, port: Port):
        remote_port = port.forward_rule.config.get('remote_port')
        remote_address = port.forward_rule.config.get('remote_address')
        if is_ipv6(remote_address):
            remote_address = f"[{remote_address}]"
        relay_type = port.forward_rule.config.get('type')
        args = []
        if relay_type in ("ALL", "TCP"):
            args.append(f"socat TCP6-LISTEN:{port.num},fork,reuseaddr TCP:{remote_address}:{remote_port}")
        if relay_type in ("ALL", "UDP"):
            args.append(f"socat -T 120 UDP6-LISTEN:{port.num},fork,reuseaddr UDP:{remote_address}:{remote_port}")
        args = " & ".join(args)
        return f'/bin/sh -c \\"{args}\\"'

    @property
    def playbook(self):
        return "app.yml"
