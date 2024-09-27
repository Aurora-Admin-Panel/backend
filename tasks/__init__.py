from app.utils.ip import get_external_ip
from app.core import config


from .config import huey

from .ansible import *
from .app import *
from .artifacts import *
from .clean import *
from .iptables import *
from .server import *
from .tc import *
from .traffic import *

ansible_hosts_runner()
servers_runner(prepare_services=True, sync_scripts=True, init_iptables=True)