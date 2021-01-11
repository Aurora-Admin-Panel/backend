from sqlalchemy.orm import Session

from app.db.models.port import Port

from app.db.models.port_forward import MethodEnum
from app.utils.caddy import generate_caddy_config
from tasks.functions.base import AppConfig


class CaddyConfig(AppConfig):
    method = MethodEnum.CADDY

    def __init__(self):
        super().__init__()

        self.app_name = "caddy"
        self.app_version_arg = "version"
        self.app_role_name = "caddy"
        self.app_download_role_name = "caddy_download"
        self.app_sync_role_name = "caddy_sync"

        self.traffic_meter = False
        self.update_status = True

    def apply(self, db: Session, port: Port):
        self.local_port = port.num

        caddy_config = generate_caddy_config(port)
        with open(f"ansible/project/roles/app/files/caddy-{port.id}", "w") as f:
            f.write(caddy_config)
        self.app_config = f"caddy-{port.id}"

        self.update_app = not port.server.config.get("caddy")
        self.applied = True
        return self

    @property
    def playbook(self):
        return "app.yml"
