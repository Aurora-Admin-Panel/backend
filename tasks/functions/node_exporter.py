from sqlalchemy.orm import Session

from app.db.models.port import Port

from app.db.models.port_forward import MethodEnum
from tasks.functions.base import AppConfig


class NodeExporterConfig(AppConfig):
    method = MethodEnum.NODE_EXPORTER

    def __init__(self):
        super().__init__()
        self.app_name = "node_exporter"
        self.app_version_arg = "--version"

        self.app_get_role_name = "node_exporter_get"
        self.app_sync_role_name = "node_exporter_sync"
        self.app_download_role_name = "node_exporter_download"

    def apply(self, db: Session, port: Port):
        self.local_port = port.num
        self.app_command = f'/usr/local/bin/node_exporter --web.listen-address=:{port.num} --collector.iptables'
        self.update_app = not port.server.config.get("node_exporter")
        self.applied = True
        return self

    @property
    def playbook(self):
        return "app.yml"
