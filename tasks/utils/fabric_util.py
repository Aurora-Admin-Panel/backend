import pathlib
from contextlib import contextmanager

from patchwork.files import exists
from paramiko.ssh_exception import SSHException
from fabric import Connection, Config

from app.db.session import db_session
from app.db.crud.server import get_server
from tasks.utils.files import get_md5_for_file


class AuroraConnection(Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def sudo(self):
        return self.user != 'root'

    def run(self, *args, **kwargs):
        # Hacky and maybe buggy
        # when we actually want to use 'sudo' specific args
        if self.sudo:
            return super().sudo(*args, **kwargs)
        return super().run(*args, **kwargs)

    def ensure_file(self, local_path: str, remote_path: str, ensure_same: bool = True) -> int:
        if not pathlib.Path.exists(local_path):
            print(f"{local_path} does not exist")
            return False

        if exists(self, remote_path, sudo=self.sudo):
            if ensure_same:
                local_md5 = get_md5_for_file(local_path)
                remote_md5 = self.run(f"md5sum {remote_path}").stdout.strip()
                if remote_md5 == local_md5:
                    return True
            else:
                return True

        self.put(local_path, remote_path)
        return True


@contextmanager
def connect(server_id: int, **kwargs) -> AuroraConnection:
    with db_session() as db:
        server = get_server(db, server_id)
    try:
        config = {}
        if server.sudo_password:
            config["sudo"] = {"password": server.sudo_password}
        connect_kwargs = {}
        if server.ssh_password:
            connect_kwargs["password"] = server.ssh_password
        if server.key_filename:
            connect_kwargs["key_filename"] = server.key_filename

        yield AuroraConnection(
            host=server.host,
            user=server.user,
            port=server.port,
            connect_kwargs=connect_kwargs,
            config=Config(overrides=config),
            **kwargs
        )
    except SSHException as e:
        raise e
    finally:
        pass
    