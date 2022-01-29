from sqlalchemy.orm import Session

from app.db.models.port import Port

from app.db.models.port_forward import MethodEnum

from tasks.functions.base import AppConfig


class RealmConfig(AppConfig):
    method = MethodEnum.REALM

    def __init__(self):
        super().__init__()
        self.app_name = "realm"
        self.app_version_arg = "--version"

        self.app_sync_role_name = "realm_sync"

    def apply(self, db: Session, port: Port):
        self.local_port = port.num
        self.app_command = self.get_app_command(db, port)
        self.update_app = not port.server.config.get("realm")
        self.applied = True
        return self

    def get_app_command(self, db: Session, port: Port):
        remote_address = port.forward_rule.config.get('remote_address')
        remote_port = port.forward_rule.config.get('remote_port')

        return (
            f"/usr/local/bin/realm "
            f"-l 0.0.0.0:{port.num} "
            f"-uzr {remote_address}:{remote_port}"
        )

    @property
    def playbook(self):
        return "app.yml"
