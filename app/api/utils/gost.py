import json
import typing as t
from sqlalchemy import and_
from urllib.parse import urlencode

from app.tasks import celery_app
from app.db.session import SessionLocal
from app.db.schemas.port_forward import PortForwardRuleOut
from app.db.models.port import Port
from app.db.models.port_forward import MethodEnum, PortForwardRule


def send_gost_rule(
    rule: PortForwardRule,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
    update_gost: bool = False,
):
    kwargs = {
        "rule_id": rule.id,
        "host": rule.port.server.ansible_host,
        "update_gost": update_gost,
        "update_status": new and new.method == MethodEnum.GOST,
    }
    print(f"Sending gost_runner task, kwargs: {kwargs}")
    celery_app.send_task("app.tasks.gost.gost_runner", kwargs=kwargs)


def generate_gost_config(rule: PortForwardRule) -> t.Dict:
    return {
        "Retries": rule.config.get("Retries", 1),
        "ServeNodes": rule.config.get(
            "ServeNodes", [f":{rule.port.internal_num}"]
        ),
        "ChainNodes": rule.config.get("ChainNodes", []),
    }


def get_gost_config(rule_id: int) -> t.Dict:
    db = SessionLocal()
    rule = (
        db.query(PortForwardRule).filter(PortForwardRule.id == rule_id).first()
    )
    rules = (
        db.query(PortForwardRule)
        .join(Port)
        .filter(
            and_(
                PortForwardRule.method == MethodEnum.GOST,
                Port.server_id == rule.port.server_id,
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
