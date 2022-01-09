import traceback

from app.db.session import db_session
from app.db.models.port_forward import MethodEnum
from app.db.crud.server import (
    get_server,
    get_server_with_ports_usage,
)
from app.db.crud.port import get_port
from app.db.crud.port_forward import get_all_ddns_rules
from app.utils.dns import dns_query
from app.utils.ip import is_ip

from tasks import celery_app
from tasks.app import rule_runner
from tasks.utils.runner import run
from tasks.utils.server import iptables_restore_service_enabled
from tasks.utils.handlers import status_handler, iptables_finished_handler


@celery_app.task(priority=0)
def iptables_runner(
    port_id: int,
    server_id: int,
    local_port: int,
    remote_address: str,
    remote_port: int = None,
    forward_type: str = None,
    update_status: bool = False,
):
    try:
        if not is_ip(remote_address):
            remote_ip = dns_query(remote_address)
        else:
            remote_ip = remote_address
        with db_session() as db:
            port = get_port(db, server_id, port_id)
            if not forward_type:
                args = f" delete {local_port}"
            elif remote_port:
                port.forward_rule.config["remote_ip"] = remote_ip
                db.add(port.forward_rule)
                db.commit()
                args = f" -t={forward_type} forward {local_port} {remote_ip} {remote_port}"
            else:
                args = f" list {local_port}"
            server = get_server_with_ports_usage(db, server_id)

        extravars = {
            "host": server.ansible_name,
            "local_port": local_port,
            "iptables_args": args,
            "init_iptables": not iptables_restore_service_enabled(
                server.config
            ),
        }

        return run(
            server=server,
            playbook="iptables.yml",
            extravars=extravars,
            status_handler=lambda s, **k: status_handler(
                port_id, s, update_status
            ),
            finished_callback=iptables_finished_handler(server, port_id, True)
            if update_status
            else lambda r: None,
        )
    except Exception:
        traceback.print_exc()
        with db_session() as db:
            port = get_port(db, server_id, port_id)
            port.forward_rule.status = "failed"
            port.forward_rule.config["error"] = traceback.format_exc()
            print(port.forward_rule.__dict__)
            db.add(port.forward_rule)
            db.commit()


@celery_app.task()
def iptables_reset_runner(
    server_id: int,
    port_num: int,
):
    with db_session() as db:
        server = get_server(db, server_id)
    extravars = {
        "host": server.ansible_name,
        "local_port": port_num,
        "iptables_args": f" reset {port_num}",
    }

    return run(
        server=server,
        playbook="iptables.yml",
        extravars=extravars,
    )


@celery_app.task()
def ddns_runner():
    with db_session() as db:
        rules = get_all_ddns_rules(db)
    for rule in rules:
        if (
            rule.config.get("remote_address")
            and rule.config.get("remote_ip")
            and not is_ip(rule.config.get("remote_address"))
        ):
            updated_ip = dns_query(rule.config["remote_address"])
            if updated_ip and updated_ip != rule.config["remote_ip"]:
                print(
                    f"DNS changed for address {rule.config['remote_address']}, "
                    + f"{rule.config['remote_ip']}->{updated_ip}"
                )
                if rule.method == MethodEnum.IPTABLES:
                    iptables_runner.delay(
                        rule.port.id,
                        rule.port.server.id,
                        rule.port.num,
                        remote_address=updated_ip,
                        remote_port=rule.config["remote_port"],
                        forward_type=rule.config.get("type", "ALL"),
                        update_status=True,
                    )
                else:
                    rule_runner.delay(rule_id=rule.id)
