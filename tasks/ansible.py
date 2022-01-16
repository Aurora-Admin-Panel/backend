from tasks.config import huey
from app.db.session import db_session
from app.db.models.server import Server


@huey.task(priority=10)
def ansible_hosts_runner():
    with db_session() as db:
        servers = db.query(Server).filter(Server.is_active==True).all()

    with open("ansible/inventory/hosts", 'w+') as f:
        f.write("### START AUTO GENERATION ###\n")
        for server in servers:
            f.write(
                f"{server.ansible_name}"
                f"\tansible_host={server.ansible_host}"
                f"\tansible_port={server.ansible_port}"
                f"\tansible_user={server.ansible_user}\n"
            )
        f.write("### END AUTO GENERATION ###")
