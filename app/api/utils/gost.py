import json
import typing as t
from sqlalchemy import and_, or_
from urllib.parse import urlencode

from app.tasks import celery_app
from app.db.session import SessionLocal
from app.db.schemas.port_forward import PortForwardRuleOut
from app.db.models.port import Port
from app.db.models.server import Server
from app.db.models.port_forward import MethodEnum, PortForwardRule


def send_gost_rule(
    port_id: int,
    host: str,
    update_status: bool,
    update_gost: bool = False,
):
    kwargs = {
        "port_id": port_id,
        "host": host,
        "update_status": update_status,
        "update_gost": update_gost,
    }
    print(f"Sending gost_runner task, kwargs: {kwargs}")
    celery_app.send_task("app.tasks.gost.gost_runner", kwargs=kwargs)


def generate_gost_config(rule: PortForwardRule) -> t.Dict:
    return {
        "Retries": rule.config.get("Retries", 0),
        "ServeNodes": rule.config.get(
            "ServeNodes", [f":{rule.port.internal_num}"]
        ),
        "ChainNodes": rule.config.get("ChainNodes", []),
    }


def get_gost_config(host: int) -> t.Dict:
    db = SessionLocal()
    server = (
        db.query(Server)
        .filter(
            or_(
                Server.address == host,
                Server.ansible_name == host,
                Server.ansible_host == host,
            )
        )
        .first()
    )
    config = {}
    if server:
        rules = (
            db.query(PortForwardRule)
            .join(Port)
            .filter(
                and_(
                    PortForwardRule.method == MethodEnum.GOST,
                    Port.server_id == server.id,
                )
            )
            .all()
        )
        config = {
            "Retries": 0,
            "ServeNodes": [],
            "ChainNodes": [],
            "Routes": list(map(generate_gost_config, rules)),
        }
    return config
