from pathlib import Path
from typing import Union
import shlex


def q(s: str | Path) -> str:
    return shlex.quote(str(s))
