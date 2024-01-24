from sqlalchemy.orm import Session

from app.db.models import Port
from app.db.models import MethodEnum
from app.utils.dns import dns_query
from app.utils.ip import is_ip, is_ipv6
from tasks.functions.base import AppConfig


class BrookConfig(AppConfig):
    method = MethodEnum.BROOK

    def __init__(self):
        super().__init__()
        self.app_name = "brook"
        self.app_path = "/usr/local/bin/"
        self.app_sync_role_name = "brook_sync"


    def apply(self, db: Session, port: Port):
        self.local_port = port.num
        self.app_command = self.get_app_command(db, port)
        self.update_app = not port.server.config.get("brook")
        self.applied = True
        return self

    def get_app_command(self, db: Session, port: Port):
        command = port.forward_rule.config.get("command")
        remote_address = port.forward_rule.config.get("remote_address")
        if command.endswith(("relay", "client")):
            remote_ip = dns_query(remote_address)
            port.forward_rule.config['remote_ip'] = remote_ip
            db.add(port.forward_rule)
            db.commit()
            if is_ipv6(remote_ip):
                remote_ip = f"[{remote_ip}]"
        if command == "relay":
            args = (
                f"{command} "
                f"-f :{port.num} "
                f"-t {remote_ip}:{port.forward_rule.config.get('remote_port')}"
            )
        elif command.endswith("server"):
            args = f"{command} -l :{port.num} -p {port.forward_rule.config.get('password')}"
        elif command.endswith("client"):
            server_address = port.forward_rule.config.get("server_address")
            if is_ipv6(server_address):
                server_address = f"[{server_address}]"
            server_port = port.forward_rule.config.get("server_port")
            remote_port = port.forward_rule.config.get("remote_port")
            password = port.forward_rule.config.get("password")
            args = (
                f"relayoverbrook -f :{port.num} "
                f"-t {remote_ip}:{remote_port} "
                f"-p {password} "
                f"-s {'ws://' if command  == 'wsclient' else ''}"
                f"{server_address}:{server_port}"
            )
        return f"/usr/local/bin/brook {args}"

    @property
    def playbook(self):
        return "app.yml"
