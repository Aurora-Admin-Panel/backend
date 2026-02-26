from app.utils.executable_contract import compile_executable_contract_preview


def test_compile_preview_builds_argv_env_and_redacts_secret():
    contract = {
        "schemaVersion": "aurora-exec/v1",
        "contractKey": "demo_contract",
        "version": 1,
        "title": "Demo",
        "exec": {"bin": "/usr/bin/demo", "baseArgs": ["run"]},
        "params": [
            {
                "key": "mode",
                "type": "enum",
                "label": "Mode",
                "required": True,
                "options": [{"value": "tcp", "label": "TCP"}],
                "emit": {"pos": 0},
            },
            {
                "key": "port",
                "type": "int",
                "label": "Port",
                "required": True,
                "validation": {"min": 1, "max": 65535},
                "emit": {"arg": "--port"},
            },
            {
                "key": "udp",
                "type": "bool",
                "label": "UDP",
                "default": False,
                "emit": {"flag": "--udp"},
            },
            {
                "key": "password",
                "type": "secret",
                "label": "Password",
                "emit": {"env": "DEMO_PASSWORD"},
            },
        ],
    }

    result = compile_executable_contract_preview(
        contract,
        {"mode": "tcp", "port": "5201", "udp": True, "password": "abc123"},
    )

    assert result["ok"] is True
    assert result["plan"]["argv"] == ["/usr/bin/demo", "run", "tcp", "--port", "5201", "--udp"]
    assert result["plan"]["env"]["DEMO_PASSWORD"] == "abc123"
    assert result["preview"]["env"]["DEMO_PASSWORD"] == "***REDACTED***"
    assert "--udp" in result["preview"]["argv"]


def test_compile_preview_supports_file_and_stdin_emit():
    contract = {
        "schemaVersion": "aurora-exec/v1",
        "contractKey": "demo_io",
        "version": 1,
        "title": "Demo IO",
        "exec": {"bin": "/usr/bin/demo"},
        "params": [
            {
                "key": "config",
                "type": "object",
                "label": "Config",
                "properties": [
                    {
                        "key": "host",
                        "type": "string",
                        "label": "Host",
                        "required": True,
                        "emit": {"arg": "--ignored"},  # nested emit unused in v1 compile unless nested field compiled directly
                    }
                ],
                "emit": {
                    "file": {
                        "pathTemplate": "/tmp/aurora/{{jobId}}-{{paramKey}}.json",
                        "format": "json",
                    }
                },
            },
            {
                "key": "payload",
                "type": "string",
                "label": "Payload",
                "emit": {"stdin": {"format": "raw"}},
            },
        ],
    }

    result = compile_executable_contract_preview(
        contract,
        {"config": {"host": "example.com"}, "payload": "hello"},
        {"jobId": "job-1"},
    )

    assert result["ok"] is True
    assert result["plan"]["files"][0]["path"] == "/tmp/aurora/job-1-config.json"
    assert '"host":"example.com"' in result["plan"]["files"][0]["content"]
    assert result["plan"]["stdin"]["content"] == "hello"


def test_compile_preview_rejects_unknown_param():
    contract = {
        "schemaVersion": "aurora-exec/v1",
        "contractKey": "demo_contract",
        "version": 1,
        "title": "Demo",
        "exec": {"bin": "/usr/bin/demo"},
        "params": [
            {"key": "name", "type": "string", "label": "Name", "emit": {"arg": "--name"}}
        ],
    }

    result = compile_executable_contract_preview(contract, {"unknown": "x"})
    assert result["ok"] is False
    assert "Unknown parameter" in result["error"]

