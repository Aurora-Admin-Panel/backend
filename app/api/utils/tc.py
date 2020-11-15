import typing as t

from app.tasks import celery_app


def send_tc(
    host: str,
    port_id: int,
    port_num: int,
    egress_limit: int = None,
    ingress_limit: int = None):

    kwargs = {
        "host": host,
        "port_id": port_id,
        "port_num": port_num,
    }
    if egress_limit:
        kwargs['egress_limit'] = egress_limit
    if ingress_limit:
        kwargs['ingress_limit'] = ingress_limit

    print(f"Sending tc_runner task, kwargs: {kwargs}")
    celery_app.send_task("app.tasks.tc.tc_runner", kwargs=kwargs)
