import json
import socket
import traceback
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_DOH_URL = "https://cloudflare-dns.com/dns-query"


def dns_query(url: str, doh_url: str = DEFAULT_DOH_URL) -> str:
    # TODO: Support ipv6
    params = urlencode({"name": url, "type": "A"})
    req = Request(
        f"{doh_url}?{params}", headers={"accept": "application/dns-json"}
    )
    try:
        ret = urlopen(req, timeout=2)
    except (socket.timeout, URLError):
        return url
    ret = ret.read().decode("utf-8")
    result = json.loads(ret)
    if not result.get("Answer"):
        return url
    return result.get("Answer", [])[-1]["data"]
