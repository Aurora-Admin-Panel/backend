import json
import traceback
import typing as t
import ansible_runner
from uuid import uuid4
from collections import namedtuple

from app.db.session import SessionLocal
from app.db.models.port import Port
from app.db.models.user import User
from app.db.models.server import Server
from app.db.models.port_forward import PortForwardRule, MethodEnum
from app.db.crud.server import get_server
from app.db.crud.port import get_port_by_id
from app.db.crud.port_forward import get_forward_rule_by_id
from app.utils.caddy import generate_caddy_config
from app.utils.v2ray import generate_v2ray_config

from tasks import celery_app
from tasks.utils.runner import run
from tasks.utils.handlers import iptables_finished_handler, status_handler

AppConfig = namedtuple("AppConfig", ["playbook", "vars"])

default_vars = {
    "app_version_arg": "-v",
    "traffic_meter": True,
    "app_role_name": "app",
    "app_sync_role_name": "app_sync",
    "app_get_role_name": "app_get",
    "remote_ip": "ANYWHERE",
}

def get_app_config(port: Port):
    if port.forward_rule.method == MethodEnum.CADDY:
        caddy_config = generate_caddy_config(port)
        with open(f"ansible/project/roles/app/files/caddy-{port.id}", "w") as f:
            f.write(caddy_config)
        return AppConfig(
            "app.yml",
            {
                **default_vars,
                "local_port": port.num,
                "app_name": "caddy",
                "app_version_arg": "version",
                "traffic_meter": False,
                "app_role_name": "caddy",
                "app_download_role_name": "caddy_download",
                "app_sync_role_name": "caddy_sync",
                "app_config": f"caddy-{port.id}",
                "update_status": True,
                "update_app": not port.server.config.get("caddy"),
            },
        )
    elif port.forward_rule.method == MethodEnum.IPERF:
        return AppConfig(
            "app.yml",
            {
                **default_vars,
                "local_port": port.num,
                "app_name": "iperf",
                "app_version_arg": "-version",
                "traffic_meter": True,
                "app_command": f"/usr/bin/iperf3 -s -p {port.num}",
                "app_download_role_name": "void",
                "app_get_role_name": "iperf_get",
                "app_sync_role_name": "iperf_install",
                "update_status": True,
                "update_app": not port.server.config.get("iperf"),
            },
        )
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
