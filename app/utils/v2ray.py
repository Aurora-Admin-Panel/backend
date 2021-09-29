import typing as t

from app.db.models.port_forward import MethodEnum, PortForwardRule


def generate_v2ray_config(rule: PortForwardRule) -> t.Dict:
    if rule.method != MethodEnum.V2RAY:
        return {}
    inbound = rule.config.get("inbound", {})
    inbound["port"] = rule.port.num
    return {
        "inbounds": [inbound],
        "outbounds": [rule.config.get("outbound", {})],
        "routing": rule.config.get("routing", {}),
        "dns": rule.config.get("dns", {}),
        "log": {"loglevel": "warning","access":"none"},
    }
