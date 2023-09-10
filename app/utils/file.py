from datetime import datetime
from pathlib import Path
from uuid import uuid4

import aiofiles
from strawberry.file_uploads import Upload

from app.core.config import FILE_STORAGE_PATH
from app.db.models import FileTypeEnum


async def store_file(file: Upload, type: FileTypeEnum) -> Path:
    now = datetime.utcnow()
    storage_path = Path(FILE_STORAGE_PATH).joinpath(
        str(now.year),
        str(now.month),
        str(now.day),
        f"{uuid4().hex}-{file.filename}",
    )
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.touch(
        exist_ok=True,
        mode=0o600
        if type == FileTypeEnum.SECRET
        else (0o766 if type == FileTypeEnum.EXECUTABLE else 0o644),
    )
    async with aiofiles.open(storage_path, "wb") as f:
        await f.write(await file.read())
    return storage_path
