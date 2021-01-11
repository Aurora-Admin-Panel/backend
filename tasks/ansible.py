from tasks import celery_app
from app.db.session import get_db
from app.db.models.server import Server


@celery_app.task()
def ansible_hosts_runner():
    db = next(get_db())
    servers = db.query(Server).filter(Server.is_active == True).all()

    with open("ansible/inventory/hosts", 'w+') as f:
        f.write("### START AUTO GENERATION ###\n")
        for server in servers:
            f.write(
                f"{server.ansible_name}\tansible_host={server.ansible_host}\tansible_port={server.ansible_port}\tansible_user={server.ansible_user}\n"
            )
        f.write("### END AUTO GENERATION ###")
