from celery import Celery
from celery.schedules import crontab

celery_app = Celery("worker", broker="redis://redis:6379/0")

celery_app.conf.task_routes = {"app.tasks.*": "main-queue"}

celery_app.autodiscover_tasks(
    [
        "app.tasks.ansible",
        "app.tasks.traffic",
        "app.tasks.example",
        "app.tasks.iptables",
        "app.tasks.gost",
        "app.tasks.tc",
    ]
)

# celery_app.conf.beat_schedule = {
#     'run-every-minute': {
#         'task': 'app.tasks.example.example_task',
#         'schedule': crontab(),
#         'args': ('world', )
#     }
# }