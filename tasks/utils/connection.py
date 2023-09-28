import socket
import pathlib
from contextlib import contextmanager

from app.db.crud.server import get_server
from app.db.session import db_session
from app.core import config
from fabric import Config, Connection
from fabric.exceptions import GroupException
from paramiko.rsakey import RSAKey
from tasks.utils.exception import AuroraException
from patchwork.files import exists
from tasks.utils.files import get_md5_for_file


class AuroraConnection(Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def sudo(self):
        return self.user != "root"

    def run(self, *args, **kwargs):
        # Hacky and maybe buggy
        # when we actually want to use 'sudo' specific args
        if self.sudo:
            return super().sudo(*args, pty=True, **kwargs)
        return super().run(*args, pty=True, **kwargs)

    def ensure_file(
        self, local_path: str, remote_path: str, ensure_same: bool = True
    ) -> None:
        if not pathlib.Path.exists(local_path):
            raise AuroraException(f"{local_path} does not exist")

        if exists(self, remote_path, sudo=self.sudo):
            if ensure_same:
                local_md5 = get_md5_for_file(local_path)
                remote_md5 = self.run(f"md5sum {remote_path}").stdout.strip()
                if remote_md5 == local_md5:
                    return
        self.put(local_path, remote_path)


@contextmanager
def connect(server_id: int, **kwargs) -> AuroraConnection:
    with db_session() as db:
        server = get_server(db, server_id)

    if not server:
        raise AuroraException(f"Server with id {server_id} does not exist")
    try:
        connect_kwargs = {}
        if server.ssh_password:
            connect_kwargs["password"] = server.ssh_password
        if server.key_file:
            connect_kwargs["pkey"] = RSAKey.from_private_key_file(
                server.key_file.storage_path
            )
            # connect_kwargs["key_filename"] = server.key_file.storage_path

        connection_config = {}
        if server.sudo_password:
            connection_config["sudo"] = {"password": server.sudo_password}

        yield AuroraConnection(
            host=server.host,
            user=server.user,
            port=server.port,
            connect_timeout=config.SSH_CONNECTION_TIMEOUT,
            connect_kwargs=connect_kwargs,
            config=Config(overrides=connection_config),
            **kwargs,
        )
    except GroupException as e:
        print(e.with_traceback())
        import traceback

        traceback.print_exc()
        raise AuroraException(f"Failed to connect to host: {e}")
    except socket.timeout as e:
        print(e)
        import traceback

        traceback.print_exc()
        raise AuroraException("Connection timed out")
    except Exception as e:
        print(e)
        import traceback

        traceback.print_exc()
        raise AuroraException(f"Failed to connect to host: {e}")
