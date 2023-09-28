import sentry_sdk

from app.utils.ip import get_external_ip
from app.core import config


if config.ENABLE_SENTRY:
    sentry_sdk.init(
        release=f"{config.BACKEND_VERSION}",
        environment=f"{config.ENVIRONMENT}",
        dsn="https://e0216ee884d643dd90778833b0f99abd@sentry.leishi.io/3",
        traces_sample_rate=1.0,
    )
    sentry_sdk.set_tag("panel.ip", get_external_ip())


from .config import huey

from .ansible import *
from .app import *
from .artifacts import *
from .clean import *
from .iptables import *
from .server import *
from .tc import *
from .traffic import *
from .test import *
