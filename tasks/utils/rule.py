import json
from collections import namedtuple

from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule, MethodEnum

from tasks.functions.base import AppConfig
from tasks.functions.brook import BrookConfig
from tasks.functions.caddy import CaddyConfig


def get_app_config(port: Port) -> AppConfig:
    if port.forward_rule.method == MethodEnum.BROOK:
        return BrookConfig(port)
    elif port.forward_rule.method == MethodEnum.CADDY:
        return CaddyConfig(port)
    elif port.forward_rule.method == MethodEnum.IPERF:
        return
    elif port.forward_rule.method == MethodEnum.V2RAY:
        v2ray_config = generate_v2ray_config(port.forward_rule)
        with open(
            f"ansible/project/roles/app/files/v2ray-{port.id}", "w"
        ) as f:
            f.write(json.dumps(v2ray_config, indent=2))
        return AppConfig(
            "app.yml",
            {
                **default_vars,
                "local_port": port.num,
                "app_name": "v2ray",
                "app_version_arg": "-version",
                "app_download_role_name": "v2ray_download",
                "app_command": f"/usr/local/bin/v2ray -config /usr/local/etc/aurora/{port.num}",
                "app_config": f"v2ray-{port.id}",
                "update_status": True,
                "update_app": not port.server.config.get("v2ray"),
            },
        )
    else:
        AppConfig("app.yml", {})


def get_clean_port_config(port: Port):
    return AppConfig(
        "clean_port.yml", 
        {
            "local_port": port.num
        })
