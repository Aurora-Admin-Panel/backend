import traceback
import typing as t
from uuid import uuid4
from datetime import datetime, timedelta

from app.db.session import db_session
from app.db.crud.server import get_server_with_ports_usage
from app.db.crud.port import get_port_by_id
from app.db.crud.port_forward import get_forward_rule_by_id

from .config import huey
from tasks.clean import clean_port_runner
from tasks.functions import AppConfig
from tasks.utils.runner import run
from tasks.utils.server import iptables_restore_service_enabled
from tasks.utils.handlers import iptables_finished_handler, status_handler


@huey.task()
def app_runner(
    port_id: int,
    server_id: int,
    port_num: int,
    app_name: str,
    app_command: str = None,
    app_config: t.Dict = None,
    app_version_arg: str = "-v",
    traffic_meter: bool = True,
    app_role_name: str = "app",
    app_download_role_name: str = None,
    app_sync_role_name: str = "app_sync",
    app_get_role_name: str = "app_get",
    remote_ip: str = "ANYWHERE",
    ident: str = None,
    update_status: bool = False,
):
    with db_session() as db:
        server = get_server_with_ports_usage(db, server_id)
    extravars = {
        "host": server.ansible_name,
        "local_port": port_num,
        "remote_ip": remote_ip,
        "app_name": app_name,
        "app_command": app_command,
        "app_version_arg": app_version_arg,
        "traffic_meter": traffic_meter,
        "app_download_role_name": app_download_role_name
        if app_download_role_name is not None
        else f"{app_name}_download",
        "app_role_name": app_role_name,
        "app_sync_role_name": app_sync_role_name,
        "app_get_role_name": app_get_role_name,
        "update_status": update_status,
        "update_app": update_status and not server.config.get(app_name),
        "init_iptables": not iptables_restore_service_enabled(server.config),
    }
    if app_config is not None:
        with open(
            f"ansible/project/roles/app/files/{app_name}-{port_id}", "w"
        ) as f:
            f.write(app_config)
        extravars["app_config"] = f"{app_name}-{port_id}"

    run(
        server=server,
        playbook="app.yml",
        extravars=extravars,
        ident=ident,
        status_handler=lambda s, **k: status_handler(port_id, s, update_status),
        finished_callback=iptables_finished_handler(server.id, port_id, True)
        if update_status
        else lambda r: None,
    )


@huey.task()
def rule_runner(rule_id: int):
    try:
        with db_session() as db:
            rule = get_forward_rule_by_id(db, rule_id)
            port_id, port_num, server_id = (
                rule.port.id,
                rule.port.num,
                rule.port.server.id,
            )
            ident = uuid4()
            app_configs = []
            if rule.config.get("reverse_proxy"):
                reverse_proxy_port = get_port_by_id(
                    db, rule.config.get("reverse_proxy")
                )
                app_configs.append(
                    AppConfig.configs[
                        reverse_proxy_port.forward_rule.method
                    ].apply(db, reverse_proxy_port)
                )
            app_configs.append(
                AppConfig.configs[rule.method].apply(db, rule.port)
            )
            db.refresh(rule)
            server = get_server_with_ports_usage(db, server_id)

        for config in app_configs:
            runner = run(
                server,
                config.playbook,
                extravars=config.extravars,
                ident=ident,
                status_handler=lambda s, **k: status_handler(port_id, s, True),
                finished_callback=iptables_finished_handler(
                    server.id, port_id, True
                ),
            )
            if runner.status != "successful":
                break
        if rule.config.get("expire_second"):
            clean_port_runner(
                (server_id, port_num),
                eta=datetime.now()
                + timedelta(seconds=rule.config.get("expire_second")),
            )
    except Exception:
        with db_session() as db:
            rule.status = "failed"
            rule.config["error"] = traceback.format_exc()
            db.add(rule)
            db.commit()
