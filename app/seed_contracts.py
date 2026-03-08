"""Seed built-in executable contracts.

Run via: docker-compose exec backend python3 app/seed_contracts.py
"""

from app.db.session import db_session
from app.db.models import ExecutableContract

BUILTIN_CONTRACTS = [
    {
        "schemaVersion": "aurora-exec/v1",
        "contractKey": "gost",
        "version": 1,
        "title": "GOST",
        "description": "GO Simple Tunnel - a simple tunnel written in golang",
        "exec": {
            "bin": "gost",
            "baseArgs": [],
            "source": {
                "type": "github",
                "repo": "go-gost/gost",
                "assetPattern": "gost_*_linux_{arch}.tar.gz",
                "extractPath": "gost",
            },
        },
        "params": [
            {
                "key": "args",
                "type": "string",
                "label": "Arguments",
                "description": "Command-line arguments for gost",
                "required": False,
                "emit": {"arg": "-L"},
            }
        ],
    },
    {
        "schemaVersion": "aurora-exec/v1",
        "contractKey": "realm",
        "version": 1,
        "title": "Realm",
        "description": "A network relay tool",
        "exec": {
            "bin": "realm",
            "baseArgs": [],
            "source": {
                "type": "github",
                "repo": "zhboner/realm",
                "assetPattern": "realm-*-linux-gnu-{arch}*",
            },
        },
        "params": [
            {
                "key": "config",
                "type": "string",
                "label": "Config File Content",
                "description": "TOML config for realm",
                "required": False,
                "emit": {
                    "file": {
                        "pathTemplate": "{{workingDir}}/realm.toml",
                        "format": "raw",
                    },
                },
            },
            {
                "key": "config_path",
                "type": "string",
                "label": "Config Path",
                "description": "Path to config file",
                "default": "realm.toml",
                "required": False,
                "emit": {"arg": "-c"},
            },
        ],
    },
    {
        "schemaVersion": "aurora-exec/v1",
        "contractKey": "caddy",
        "version": 1,
        "title": "Caddy",
        "description": "Fast and extensible multi-platform HTTP/1-2-3 web server with automatic HTTPS",
        "exec": {
            "bin": "caddy",
            "baseArgs": ["run"],
            "source": {
                "type": "github",
                "repo": "caddyserver/caddy",
                "assetPattern": "caddy_*_linux_{arch}.tar.gz",
                "extractPath": "caddy",
            },
        },
        "params": [
            {
                "key": "config_path",
                "type": "string",
                "label": "Config Path",
                "description": "Path to Caddyfile",
                "default": "Caddyfile",
                "required": False,
                "emit": {"arg": "--config"},
            }
        ],
    },
    {
        "schemaVersion": "aurora-exec/v1",
        "contractKey": "brook",
        "version": 1,
        "title": "Brook",
        "description": "A cross-platform programmable network tool",
        "exec": {
            "bin": "brook",
            "baseArgs": [],
            "source": {
                "type": "github",
                "repo": "txthinking/brook",
                "assetPattern": "brook_linux_{arch}",
            },
        },
        "params": [
            {
                "key": "command",
                "type": "string",
                "label": "Command",
                "description": "Brook subcommand (e.g. server, relay)",
                "required": True,
                "emit": {"pos": 0},
            },
            {
                "key": "args",
                "type": "string",
                "label": "Arguments",
                "description": "Additional arguments",
                "required": False,
                "emit": {"pos": 1},
            },
        ],
    },
]


def seed_builtin_contracts():
    """Upsert built-in contracts (idempotent by contract_key + version)."""
    with db_session() as db:
        for contract_data in BUILTIN_CONTRACTS:
            key = contract_data["contractKey"]
            version = contract_data["version"]

            existing = (
                db.query(ExecutableContract)
                .filter_by(contract_key=key, version=version)
                .first()
            )

            if existing:
                existing.title = contract_data["title"]
                existing.description = contract_data.get("description")
                existing.schema_json = contract_data
                existing.is_builtin = True
                existing.is_active = True
            else:
                row = ExecutableContract(
                    contract_key=key,
                    version=version,
                    title=contract_data["title"],
                    description=contract_data.get("description"),
                    schema_json=contract_data,
                    is_builtin=True,
                    is_active=True,
                )
                db.add(row)

        db.commit()
        print(f"Seeded {len(BUILTIN_CONTRACTS)} built-in contracts.")


if __name__ == "__main__":
    seed_builtin_contracts()
