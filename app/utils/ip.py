import re
import httpx


def get_external_ip() -> str:
    # TODO: handle exception
    return httpx.get('https://api.ipify.org').text

def is_ip(maybe_ip: str) -> bool:
    return re.match(r'^((25[0-5]|(2[0-4]|1[0-9]|[1-9]|)[0-9])(\.(?!$)|$)){4}$', maybe_ip)

