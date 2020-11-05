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


def get_gost_config(port_id: int) -> t.Tuple[int, t.Dict]:
    db = SessionLocal()
    port = db.query(Port).filter(Port.id == port_id).first()
    # Here we will use only the first rule.
    if (
        port
        and len(port.port_forward_rules) > 0
        and port.port_forward_rules[0].method == MethodEnum.GOST
    ):
        return port.internal_num, generate_gost_config(
            port.port_forward_rules[0]
        )
    return port.internal_num, {}
