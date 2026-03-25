from pathlib import Path, PurePosixPath
from typing import Union
import shlex


def q(s: str | Path | PurePosixPath) -> str:
    if isinstance(s, str):
        return shlex.quote(s)
    elif isinstance(s, Path):
        return shlex.quote(str(s.as_posix()))
    return shlex.quote(str(s))
