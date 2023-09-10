import os
from shutil import rmtree

from huey import crontab

from .config import huey


@huey.periodic_task(crontab(minute='0', hour='*'))
def clean_artifacts_runner():
    for d in os.listdir('ansible/priv_data_dirs'):
        rmtree(f"ansible/priv_data_dirs/{d}/artifacts", ignore_errors=True)
    print("Artifacts all cleaned")
