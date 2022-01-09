import os
import json
import socket
import traceback
from typing import Optional
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


import dns.resolver


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


def get_ipv4_by_aliyun(hostname: str) -> Optional[str]:
    params = urlencode({"name": hostname, "type": "1"})
    req = Request(
        f"https://dns.alidns.com/resolve?{params}",
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
    return result.get("Answer", [])[-1]["data"]


def get_ipv4_by_cloudflare(hostname: str) -> Optional[str]:
    params = urlencode({"name": hostname, "type": "A"})
    req = Request(
        f"https://cloudflare-dns.com/dns-query?{params}",
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
    return result.get("Answer", [])[-1]["data"]


def dns_query(hostname: str) -> Optional[str]:
    # TODO: Support ipv6
    if custom_dns := os.environ.get('DNS_SERVER', None):
        if result := get_ipv4_by_custom_server(hostname, custom_dns):
            return result
    if result := get_ipv4_by_cloudflare(hostname):
        return result
    if result := get_ipv4_by_aliyun(hostname):
        return result
    if result := get_ipv4_by_system(hostname):
        return result
    return None
