import os
import json
import socket
import traceback
from typing import Optional
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import dns.resolver

from app.utils.ip import is_ip, is_ipv6


def get_ipv4_by_custom_server(hostname: str, dns_server: str) -> Optional[str]:
    if ':' in dns_server:
        if len(dns_server.split(':')) == 2:
            server, port = dns_server.split(':')
        else:
            return None
    else:
        server, port = dns_server, None
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [server]
    if port:
        resolver.port = port

    try:
        answer = resolver.query(hostname)
    except:
        return None
    return next(iter(str(a) for a in answer))


def get_ipv4_by_system(hostname: str) -> Optional[str]:
    try:
        return next(
            iter(
                list(
                    i[4][0]
                    for i in socket.getaddrinfo(hostname, 0)
                    if i[0] is socket.AddressFamily.AF_INET
                    and i[1] is socket.SocketKind.SOCK_RAW
                )
            )
        )
    except:
        return None


def get_by_doh(
        hostname: str,
        query_host: str = "cloudflare",
        dns_type: str = "A"
    ) -> Optional[str]:
    doh_url = {
        "cloudflare": "https://cloudflare-dns.com/dns-query",
        "aliyun": "https://dns.alidns.com/resolve",
    }
    query_url = doh_url.get(query_host)
    if not query_url:
        raise ValueError
    if dns_type not in ("A", "AAAA"):
        raise ValueError
    params = urlencode({"name": hostname, "type": dns_type})
    req = Request(
        f"{query_url}?{params}",
        headers={"accept": "application/dns-json"},
    )
    try:
        ret = urlopen(req, timeout=2)
    except (socket.timeout, URLError):
        return None
    ret = ret.read().decode("utf-8")
    result = json.loads(ret)
    if not result.get("Answer"):
        return None
    if (answer := result.get("Answer")):
        if (answer := answer[-1].get("data")):
            return answer
    return None


def get_ipv4(hostname: str) -> Optional[str]:
    if custom_dns := os.environ.get('DNS_SERVER', None):
        if result := get_ipv4_by_custom_server(hostname, custom_dns):
            return result
    if result := get_by_doh(hostname, "cloudflare", "A"):
        return result
    if result := get_by_doh(hostname, "aliyun", "A"):
        return result
    if result := get_ipv4_by_system(hostname):
        return result
    return None


def get_ipv6(hostname: str) -> Optional[str]:
    if result := get_by_doh(hostname, "cloudflare", "AAAA"):
        return result
    if result := get_by_doh(hostname, "aliyun", "AAAA"):
        return result
    return None


def dns_query(hostname: str) -> Optional[str]:
    hostname = hostname.strip()
    if not hostname:
        return None
    elif is_ip(hostname) or is_ipv6(hostname):
        return hostname

    if result := get_ipv4(hostname):
        return result
    if result := get_ipv6(hostname):
        return result
    return None
