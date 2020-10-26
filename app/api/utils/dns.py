import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_DOH_URL = 'https://cloudflare-dns.com/dns-query'

def dns_query(url: str, doh_url: str = DEFAULT_DOH_URL) -> str:
    # TODO: Support ipv6
    params = urlencode({'name': url, 'type': 'A'})
    req = Request(f'{doh_url}?{params}', headers={'accept': 'application/dns-json'})
    result = json.loads(urlopen(req).read().decode('utf-8'))
    if not result.get('Answer'):
        return url
    # print(url, result.get('Answer', [])[-1]['data'])
    return result.get('Answer', [])[-1]['data']