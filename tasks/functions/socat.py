from sqlalchemy.orm import Session

from app.db.models.port import Port

from app.db.models.port_forward import MethodEnum
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
        remote = f'{port.forward_rule.config.get("remote_address")}:{port.forward_rule.config.get("remote_port")}'
        if port.forward_rule.config.get("type") == "UDP":
            return f'/bin/sh -c \\"socat UDP4-LISTEN:{port.num},fork,reuseaddr UDP4:{remote}\\"'
        elif port.forward_rule.config.get("type") == "ALL":
            return (
                f'/bin/sh -c '
                f'\\"socat UDP4-LISTEN:{port.num},fork,reuseaddr UDP4:{remote} & '
                f'socat TCP4-LISTEN:{port.num},fork,reuseaddr TCP4:{remote}\\"'
            )
        return f'/bin/sh -c \\"socat TCP4-LISTEN:{port.num},fork,reuseaddr TCP4:{remote}\\"'

    @property
    def playbook(self):
        return "app.yml"
