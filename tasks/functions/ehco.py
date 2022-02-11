from sqlalchemy.orm import Session

from app.db.models.port import Port
from app.db.models.port_forward import MethodEnum
from app.utils.ip import is_ipv6
from tasks.functions.base import AppConfig


class EhcoConfig(AppConfig):
    method = MethodEnum.EHCO

    def __init__(self):
        super().__init__()
        self.app_name = "ehco"
        self.app_path = "/usr/local/bin/"
        self.app_sync_role_name = "ehco_sync"


    def apply(self, db: Session, port: Port):
        self.local_port = port.num
        self.app_command = self.get_app_command(port)
        self.update_app = not port.server.config.get("ehco")
        self.applied = True
        return self

    def get_app_command(self, port: Port):
        transport_type = port.forward_rule.config.get("transport_type", "raw")
        remote_port = port.forward_rule.config.get('remote_port')
        remote_address = port.forward_rule.config.get('remote_address')
        if is_ipv6(remote_address):
            remote_address = f"[{remote_address}]"
        args = (
            f"-l :{port.num} "
            f"--lt {port.forward_rule.config.get('listen_type', 'raw')} "
            f"-r {'wss://' if transport_type.endswith('wss') else ('ws://' if transport_type != 'raw' else '')}"
            f"{remote_address}:{remote_port} "
            f"-ur {'wss://' if transport_type.endswith('wss') else ('ws://' if transport_type != 'raw' else '')}"
            f"{remote_address}:{remote_port} "
            f"--tt {transport_type}"
        )
        return f"/usr/local/bin/ehco {args}"

    @property
    def playbook(self):
        return "app.yml"
