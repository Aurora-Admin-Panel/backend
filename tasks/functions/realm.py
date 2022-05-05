from sqlalchemy.orm import Session

from app.db.models.port import Port
from app.db.models.port_forward import MethodEnum
from app.utils.ip import is_ipv6
from tasks.functions.base import AppConfig


class RealmConfig(AppConfig):
    method = MethodEnum.REALM
    command_to_arg = {
        'tcp': "",
        'ws-in': "-b 'ws;host=abc;path=/'",
        'ws-out': "-a 'ws;host=abc;path=/'",
        "wss-in": "-b 'ws;host=abc;path=/;tls;insecure;sni=abc'",
        "wss-out": "-a 'ws;host=abc;path=/;tls;servername=abc'"
    }

    def __init__(self):
        super().__init__()
        self.app_name = "realm"
        self.app_path = "/usr/local/bin/"
        self.app_version_arg = "--version"

        self.app_sync_role_name = "realm_sync"

    def apply(self, db: Session, port: Port):
        self.local_port = port.num
        self.app_command = self.get_app_command(db, port)
        self.update_app = not port.server.config.get("realm")
        self.applied = True
        return self

    def get_app_command(self, db: Session, port: Port):
        command = port.forward_rule.config.get('command', 'tcp')
        remote_port = port.forward_rule.config.get('remote_port')
        remote_address = port.forward_rule.config.get('remote_address')
        if is_ipv6(remote_address):
            remote_address = f"[{remote_address}]"
        args = (
            f"-l [::]:{port.num} "
            f"-u "
            f"-r {remote_address}:{remote_port} "
            f"{self.command_to_arg.get(command)} "
            f"--tcp-timeout 0 "
            f"--udp-timeout 120"
        )
        return f"/usr/local/bin/realm {args}"

    @property
    def playbook(self):
        return "app.yml"
