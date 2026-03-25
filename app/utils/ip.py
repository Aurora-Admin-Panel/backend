import re
import httpx
import ipaddress


def get_external_ip() -> str:
    try:
        return httpx.get("https://api.ipify.org").text
    except Exception:
        return "NULL"


def check_ip_address(maybe_ip: str, version: int = 4) -> bool:
    if version not in (4, 6):
        raise ValueError
    try:
        ip = ipaddress.ip_address(maybe_ip)
    except ValueError:
        return False
    return ip.version == version


def is_ip(maybe_ip: str) -> bool:
    return check_ip_address(maybe_ip, 4)


def is_ipv6(maybe_ipv6: str) -> bool:
    return check_ip_address(maybe_ipv6, 6)
