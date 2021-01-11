from sqlalchemy.orm import Session

from app.db.models.port import Port

from app.db.models.port_forward import MethodEnum
from tasks.functions.base import AppConfig


class IperfConfig(AppConfig):
    method = MethodEnum.IPERF

    def __init__(self):
        super().__init__()

        self.app_name = "iperf"
        self.app_version_arg = "-version"
        self.app_download_role_name = "void"
        self.app_get_role_name = "iperf_get"
        self.app_sync_role_name = "iperf_install"

        self.traffic_meter = True
        self.update_status = True

    def apply(self, db: Session, port: Port):
        self.local_port = port.num
        self.app_command = f"/usr/bin/iperf3 -s -p {port.num}"
        self.update_app = not port.server.config.get("iperf")

        self.applied = True
        return self


    @property
    def playbook(self):
        return "app.yml"
