from datetime import timedelta

from celery import Celery
from celery.schedules import crontab, schedule
from celery.signals import celeryd_init
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration

from app.core import config

if config.ENABLE_SENTRY:
    sentry_sdk.init(
        release=f"{config.BACKEND_VERSION}",
        dsn="https://5270ad88bab643a98799d2e20a2d4c9a@o176406.ingest.sentry.io/5545255",
        traces_sample_rate=1.0,
        integrations=[CeleryIntegration()],
    )


celery_app = Celery("worker", broker="redis://redis:6379/0")

celery_app.conf.task_routes = {"tasks.*": "main-queue"}
celery_app.conf.broker_transport_options = {
    'priority_steps': list(range(10)),
    'queue_order_strategy': 'priority',
}

celery_app.autodiscover_tasks(
    [
        "tasks.ansible",
        "tasks.artifacts",
        "tasks.app",
        "tasks.ehco",
        "tasks.brook",
        "tasks.connect",
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