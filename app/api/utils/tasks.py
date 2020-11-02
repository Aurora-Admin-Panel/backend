
from app.db.models.port_forward import PortForwardRule, MethodEnum
from app.db.schemas.port_forward import PortForwardRuleOut
from app.api.utils.gost import send_gost_rule
from app.api.utils.iptables import send_iptables_forward_rule


def trigger_forward_rule(
    rule: PortForwardRule,
    old: PortForwardRuleOut = None,
    new: PortForwardRuleOut = None,
):
    print(f"Received forward rule:\nold:{old.__dict__}\nnew:{new.__dict__}")
    if (new and new.method == MethodEnum.IPTABLES) or (
        old and old.method == MethodEnum.IPTABLES
    ):
        send_iptables_forward_rule(
            rule.id,
            rule.port.server.ansible_host
            if rule.port.server.ansible_host is not None
            else rule.port.server.address,
            rule.port.internal_num
            if rule.port.internal_num is not None and rule.port.internal_num > 0
            else rule.port.num,
            old,
            new,
        )

    if (new and new.method == MethodEnum.GOST) or (
        old and old.method == MethodEnum.GOST
    ):
        send_gost_rule(rule, old, new)