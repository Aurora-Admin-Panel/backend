from sqlalchemy.orm import Session

from app.db.models.port import Port

from app.db.models.port_forward import MethodEnum
from app.utils.dns import dns_query
from app.utils.ip import is_ip

from tasks.functions.base import AppConfig


class TinyPortMapperConfig(AppConfig):
    method = MethodEnum.TINY_PORT_MAPPER

    def __init__(self):
        super().__init__()
        self.app_name = "tiny_port_mapper"
        self.app_version_arg = "-h"

        self.app_sync_role_name = "tiny_port_mapper_sync"
        self.app_download_role_name = "tiny_port_mapper_download"

    def apply(self, db: Session, port: Port):
        self.local_port = port.num
        self.app_command = self.get_app_command(db, port)
        self.update_app = not port.server.config.get("tiny_port_mapper")
        self.applied = True
        return self

    def get_app_command(self, db: Session, port: Port):
        if not is_ip(port.forward_rule.config.get('remote_address')):
            remote_ip = dns_query(port.forward_rule.config.get('remote_address'))
        else:
            remote_ip = port.forward_rule.config.get('remote_address')
        port.forward_rule.config['remote_ip'] = remote_ip
        db.add(port.forward_rule)
        db.commit()

        return (
            f"/usr/local/bin/tiny_port_mapper "
            f"--log-level 3 "
            f"--disable-color "
            f"-l0.0.0.0:{port.num} "
            f"-r{remote_ip}:{port.forward_rule.config.get('remote_port')} "
            f"{'-t ' if port.forward_rule.config.get('type') == 'ALL' or port.forward_rule.config.get('type') == 'TCP' else ''}"
            f"{'-u ' if port.forward_rule.config.get('type') == 'ALL' or port.forward_rule.config.get('type') == 'UDP' else ''}"
        )

    @property
    def playbook(self):
        return "app.yml"
