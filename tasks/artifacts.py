import os
from shutil import rmtree

from tasks import celery_app


@celery_app.task()
def clean_artifacts_runner():
    for d in os.listdir('ansible/priv_data_dirs'):
        rmtree(f"ansible/priv_data_dirs/{d}/artifacts", ignore_errors=True)
    print("Artifacts all cleaned")
