from sqlalchemy.orm import Session

from app.db.models.port import Port
from app.db.models.port_forward import MethodEnum
from app.utils.dns import dns_query
from app.utils.ip import is_ip, is_ipv6
from tasks.functions.base import AppConfig


class BrookConfig(AppConfig):
    method = MethodEnum.BROOK

    def __init__(self):
        super().__init__()
        self.app_name = "brook"
        self.app_sync_role_name = "brook_sync"


    def apply(self, db: Session, port: Port):
        self.local_port = port.num
        self.app_command = self.get_app_command(db, port)
        self.update_app = not port.server.config.get("brook")
        self.applied = True
        return self

    def get_app_command(self, db: Session, port: Port):
        command = port.forward_rule.config.get("command")
        if remote_address := port.forward_rule.config.get("remote_address"):
            remote_ip = dns_query(remote_address)
            port.forward_rule.config['remote_ip'] = remote_ip
            db.add(port.forward_rule)
            db.commit()
        if is_ipv6(remote_ip):
            remote_ip = f"[{remote_ip}]"
        if command == "relay":
            args = (
                f"-f :{port.num} "
                f"-t {remote_ip}:{port.forward_rule.config.get('remote_port')}"
            )
        elif command in ("server", "wsserver"):
            args = f"-l :{port.num} -p {port.forward_rule.config.get('password')}"
        elif command in ("client"):
            args = (
                f"--socks5 127.0.0.1:{port.num} "
                f"-s {remote_ip}:{port.forward_rule.config.get('remote_port')} "
                f"-p {port.forward_rule.config.get('password')}"
            )
        elif command in ("wsclient"):
            args = (
                f"--socks5 127.0.0.1:{port.num} "
                f"--wsserver ws://{remote_ip}:{port.forward_rule.config.get('remote_port')} "
                f"-p {port.forward_rule.config.get('password')}"
            )
        else:
            args = port.forward_rule.config.get("args")
        return f"/usr/local/bin/brook {command} {args}"

    @property
    def playbook(self):
        return "app.yml"
