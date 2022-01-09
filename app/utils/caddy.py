from collections import defaultdict

from app.db.models.port import Port


padding = """
  tls {
    protocols tls1.2 tls1.3
    ciphers TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256 TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384 TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256
    curves x25519
    alpn h2 http/1.1
  }
  header {
    Strict-Transport-Security max-age=31536000; //启用HSTS
  }
"""

def generate_caddy_config(port: Port) -> str:
    hosts = defaultdict(dict)
    for domain, ports in port.server.config.get('domains', {}).items():
        hosts[domain] = ports
    for p in port.server.ports:
        if p.forward_rule and p.forward_rule.config.get('reverse_proxy') == port.id:
            tls_settings = p.forward_rule.config.get('tls_settings', {})
            if domain := tls_settings.get('domain'):
                hosts[domain][p.num] = {
                    "path": tls_settings.get('path'),
                    "protocol": tls_settings.get('protocol'),
                }
    config = 'localhost {\n  respond "Hola, Aurora Admin Panel!"\n}\n'
    for domain, ports in hosts.items():
        config += f"{domain} {{" + padding
        for p, setting in ports.items():
            protocol = setting.get('protocol')
            path = setting.get('path')
            if not port or not path.startswith('/'):
                print(f"Malformat caddy settings: {setting}, skipping...")
                continue
            if protocol == 'ws':
                config += (
                    f"  @{p} {{\n"
                    f"    path {path}\n"
                    f"    header Connection *Upgrade*\n"
                    f"    header Upgrade websocket\n"
                    f"  }}\n"
                    f"  reverse_proxy @{p} localhost:{p} {{\n"
                    f"      transport http {{\n"
                    f"        keepalive off\n"
                    f"      }}\n"
                    f"  }}\n"
                )
            elif protocol == 'h2':
                config += (
                    f"  reverse_proxy {path} localhost:{p} {{\n"
                    f"    transport http {{\n"
                    f"      keepalive off\n"
                    f"      versions h2c\n"
                    f"    }}\n"
                    f"  }}\n"
                )
            else:
                print(f"Unknown protocol for caddy: {protocol}, skipping...")
        config += f"}}\n"
    return config
