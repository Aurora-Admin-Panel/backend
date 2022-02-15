from __future__ import annotations
from sqlalchemy.orm import Session

from app.db.models.port import Port
from app.db.models.port_forward import MethodEnum


class ConfigMount(type):
    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        if not hasattr(cls, 'configs'):
            cls.configs = {}
        else:
            cls.configs[cls.method] = cls()


class AppConfig(metaclass=ConfigMount):
    method: MethodEnum

    local_port: int
    remote_ip: str

    app_name: str
    app_path: str
    app_version_arg: str

    app_command: str
    app_config: str

    app_role_name: str
    app_download_role_name: str
    app_get_role_name: str
    app_sync_role_name: str

    update_status: bool
    update_app: bool
    traffic_meter: bool

    applied: bool

    def __init__(self):
        self.app_path = ""
        self.app_version_arg = "-v"

        self.app_role_name = "app"
        self.app_sync_role_name = "app_sync"
        self.app_get_role_name = "app_get"
        self.app_download_role_name = f"{self.method.value.lower()}_download"

        self.remote_ip = "ANYWHERE"

        self.traffic_meter = True
        self.update_status = True
        self.update_app = True

        self.applied = False


    def apply(self, db: Session, port: Port) -> AppConfig:
        raise NotImplementedError

    @property
    def playbook(self):
        raise NotImplementedError

    @property
    def extravars(self):
        if not self.applied:
            raise ValueError("Config not applied")
        return self.__dict__


if __name__ == '__main__':
    config = AppConfig('test.yml')
