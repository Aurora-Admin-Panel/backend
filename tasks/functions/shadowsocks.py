from sqlalchemy.orm import Session

from app.db.models.port import Port

from app.db.models.port_forward import MethodEnum
from tasks.functions.base import AppConfig


class ShadowsocksConfig(AppConfig):
    method = MethodEnum.SHADOWSOCKS

    def __init__(self):
        super().__init__()
        self.app_name = "shadowsocks"
        self.app_path = "/usr/local/bin/"

        self.app_get_role_name = "shadowsocks_get"
        self.app_sync_role_name = "shadowsocks_sync"

    def apply(self, db: Session, port: Port):
        self.local_port = port.num
        self.app_command = self.get_app_command(port)
        self.update_app = not port.server.config.get("shadowsocks")
        self.applied = True
        return self

    def get_app_command(self, port: Port):
        if port.forward_rule.config.get("encryption") in (
            "AEAD_AES_128_GCM",
            "AEAD_AES_256_GCM",
            "AEAD_CHACHA20_POLY1305",
        ):
            # TODO: Handle special char in password
            return (
                f"/usr/local/bin/shadowsocks_go2"
                f" -s 0.0.0.0:{port.num}"
                f" -cipher {port.forward_rule.config.get('encryption')} -password {port.forward_rule.config.get('password')}"
                f" {'-udp' if port.forward_rule.config.get('udp') else ''}"
            )
        return (
                f"/usr/local/bin/shadowsocks_go"
                f" -p {port.num} -m {port.forward_rule.config.get('encryption')} -k {port.forward_rule.config.get('password')}"
                f" {'-u' if port.forward_rule.config.get('udp') else ''}"
            )

    @property
    def playbook(self):
        return "app.yml"
