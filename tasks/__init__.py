from datetime import timedelta

from celery import Celery
from celery.schedules import crontab, schedule
from celery.signals import celeryd_init
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration

from app.utils.ip import get_external_ip
from app.core import config

if config.ENABLE_SENTRY:
    sentry_sdk.init(
        release=f"{config.BACKEND_VERSION}",
        environment=f"{config.ENVIRONMENT}",
        dsn="https://74ad2dcda2794afa9a207be8e9c17ea5@sentry.leishi.io/4",
        traces_sample_rate=1.0,
        integrations=[CeleryIntegration()],
    )
    sentry_sdk.set_tag("panel.ip", get_external_ip())


celery_app = Celery("worker", broker="redis://redis:6379/0")

celery_app.conf.task_routes = {
    "tasks.ansible.*": "high-queue",
    "tasks.app.*": "high-queue",
    "tasks.iptables.*": "high-queue",
    "tasks.tc.*": "high-queue",

    "tasks.*": "low-queue",
}
celery_app.conf.task_acks_late = True
celery_app.conf.worker_prefetch_multiplier = 1

celery_app.autodiscover_tasks(
    [
        "tasks.ansible",
        "tasks.artifacts",
        "tasks.app",
        "tasks.ehco",
        "tasks.brook",
        "tasks.clean",
        "tasks.traffic",
        "tasks.iptables",
        "tasks.server",
        "tasks.gost",
        "tasks.tc",
        "tasks.v2ray",
        "tasks.socat",
        "tasks.wstunnel",
        "tasks.shadowsocks",
        "tasks.node_exporter",
        "tasks.tiny_port_mapper",
    ]
)

celery_app.conf.beat_schedule = {
    "run-get-traffic": {
        "task": "tasks.traffic.traffic_runner",
        "schedule": schedule(timedelta(seconds=int(config.TRAFFIC_INTERVAL_SECONDS))),
    },
    "run-ddns": {
        "task": "tasks.iptables.ddns_runner",
        "schedule": schedule(timedelta(seconds=int(config.DDNS_INTERVAL_SECONDS))),
    },
    "run-clean-artifacts": {
        "task": "tasks.artifacts.clean_artifacts_runner",
        "schedule": crontab(minute=0, hour=0),
    }
}


@celeryd_init.connect
def configure_workers(sender=None, conf=None, **kwargs):
    celery_app.send_task("tasks.ansible.ansible_hosts_runner")
    celery_app.send_task(
        "tasks.server.servers_runner",
        kwargs={
            "prepare_services": True,
            "sync_scripts": True,
            "init_iptables": True,
        })
