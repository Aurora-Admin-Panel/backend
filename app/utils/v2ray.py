import typing as t

from app.db.models.port_forward import MethodEnum, PortForwardRule


def generate_v2ray_config(rule: PortForwardRule) -> t.Dict:
    if rule.method != MethodEnum.V2RAY:
        return {}
    return {
        "inbounds": rule.config.get("inbounds", []),
        "outbounds": rule.config.get("outbounds", []),
        "routing": rule.config.get("routing", {}),
        "dns": rule.config.get("dns", {}),
    }
