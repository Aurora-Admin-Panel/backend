from app.db.session import get_db
from app.db.crud.server import get_server

from tasks import celery_app
from tasks.utils.runner import run


@celery_app.task()
def tc_runner(
    server_id: int,
    port_num: int,
    egress_limit: int = None,
    ingress_limit: int = None
):
    server = get_server(next(get_db()), server_id)
    args = ""
    if egress_limit:
        args += f' -e={egress_limit}kbit'
    if ingress_limit:
        args += f' -i={ingress_limit}kbit'
    args += f' {port_num}'

    return run(
        server=server,
        playbook="tc.yml",
        extravars={"host": server.ansible_name, "tc_args": args},
    )
