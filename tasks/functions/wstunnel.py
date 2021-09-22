import typing as t
from sqlalchemy.orm import Session

from app.db.models.port import Port

from app.db.models.port_forward import MethodEnum
from tasks.functions.base import AppConfig


class WstunnelConfig(AppConfig):
    method = MethodEnum.WSTUNNEL

    def __init__(self):
        super().__init__()
        self.app_name = "wstunnel"
        self.app_version_arg = "-V"
        self.app_sync_role_name = "wstunnel_sync"
        self.app_download_role_name = "wstunnel_download"

    def apply(self, db: Session, port: Port):
        self.local_port = port.num
        self.app_command = self.get_app_command(port)
        self.update_app = not port.server.config.get("wstunnel")
        self.applied = True
        return self

    def get_app_command(self, port: Port):
        if port.forward_rule.config.get("client_type") == "client":
            return (
                f"/usr/local/bin/wstunnel "
                f"{'-u ' if port.forward_rule.config.get('forward_type') == 'UDP' else ''}"
                f"-L 0.0.0.0:{port.num}:127.0.0.1:{port.forward_rule.config.get('proxy_port')} "
                f"{port.forward_rule.config.get('protocol')}://{port.forward_rule.config.get('remote_address')}:{port.forward_rule.config.get('remote_port')} "
            )
        return (
            f"/usr/local/bin/wstunnel --server "
            f"{port.forward_rule.config.get('protocol')}://0.0.0.0:{port.num} "
            f"-r 127.0.0.1:{port.forward_rule.config.get('proxy_port')} "
        )

    @property
    def playbook(self):
        return "app.yml"
