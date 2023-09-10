from datetime import datetime
from pathlib import Path
from decimal import Decimal
from uuid import uuid4
from typing import TYPE_CHECKING, List, Optional, Dict

import aiofiles
from sqlalchemy import func
import strawberry
from strawberry.file_uploads import Upload

# from starlette.datastructures import UploadFile
from app.db.models import File as DBFile, FileTypeEnum
from app.core.config import FILE_STORAGE_PATH
from sqlalchemy import select, update, delete
from strawberry.types import Info
from .utils import PaginationWindow
from app.utils.file import store_file


count_cache: Dict[any, int] = {}


@strawberry.type
class File:
    id: int
    name: str
    type: strawberry.enum(FileTypeEnum)
    size: Decimal
    storage_path: str
    version: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    @staticmethod
    async def get_file_count(
        info: Info,
        name: Optional[str] = None,
        type: Optional[FileTypeEnum] = None,
    ) -> int:
        async_db = info.context["request"].state.async_db
        user = info.context["request"].state.user

        if user.id not in count_cache:
            stmt = select(func.count(DBFile.id))
            if not user.is_superuser:
                stmt = stmt.where(DBFile.type != FileTypeEnum.SECRET)
            if name:
                stmt = stmt.where(DBFile.name.ilike(f"%{name}%"))
            if type:
                stmt = stmt.where(DBFile.type == type)
            result = await async_db.execute(stmt)
            count_cache[(user.id, name, type)] = result.scalar()
        return count_cache[(user.id, name, type)]

    @staticmethod
    async def get_files(
        info: Info,
        name: Optional[str] = None,
        type: Optional[FileTypeEnum] = None,
    ) -> List["File"]:
        async_db = info.context["request"].state.async_db
        user = info.context["request"].state.user

        stmt = select(DBFile)
        if not user.is_superuser:
            stmt = stmt.where(DBFile.type != FileTypeEnum.SECRET)
        if name:
            stmt = stmt.where(DBFile.name.ilike(f"%{name}%"))
        if type:
            stmt = stmt.where(DBFile.type == type)
        result = await async_db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_paginated_files(
        info: Info,
        order_by: Optional[str] = "created_at",
        limit: int = 10,
        offset: int = 0,
        name: Optional[str] = None,
        type: Optional[FileTypeEnum] = None,
    ) -> PaginationWindow["File"]:
        async_db = info.context["request"].state.async_db
        user = info.context["request"].state.user

        stmt = select(DBFile).order_by(order_by)
        if not user.is_superuser:
            stmt = stmt.where(DBFile.type != FileTypeEnum.SECRET)
        if name:
            stmt = stmt.where(DBFile.name.ilike(f"%{name}%"))
        if type:
            stmt = stmt.where(DBFile.type == type)
        stmt = stmt.offset(offset).limit(limit)
        result = await async_db.execute(stmt)
        return PaginationWindow(
            items=result.scalars().unique().all(),
            count=await File.get_file_count(info, name, type),
        )

    @staticmethod
    async def upload_file(
        info: Info,
        type: FileTypeEnum,
        file: Upload,
        name: Optional[str] = None,
        version: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> "File":
        async_db = info.context["request"].state.async_db

        storage_path = await store_file(file, type)
        new_file = DBFile(
            name=name if name else file.filename,
            type=type,
            size=file.size,
            storage_path=str(storage_path),
            version=version,
            notes=notes,
        )
        async_db.add(new_file)
        await async_db.commit()
        count_cache.clear()

        return new_file

    @staticmethod
    async def update_file(
        info: Info,
        id: int,
        type: Optional[FileTypeEnum] = None,
        file: Optional[Upload] = None,
        name: Optional[str] = None,
        version: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional["File"]:
        async_db = info.context["request"].state.async_db

        stmt = update(DBFile).where(DBFile.id == id)
        if file:
            storage_path = store_file(file, type)
            stmt = stmt.values(storage_path=str(storage_path))
        if name:
            stmt = stmt.values(name=name)
        if type:
            stmt = stmt.values(type=type)
        if version:
            stmt = stmt.values(version=version)
        if notes:
            stmt = stmt.values(notes=notes)
        result = await async_db.execute(stmt)
        await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def delete_file(info: Info, id: int) -> bool:
        async_db = info.context["request"].state.async_db

        stmt = (
            delete(DBFile).where(DBFile.id == id).returning(DBFile.storage_path)
        )
        result = await async_db.execute(stmt)
        storage_path = result.scalar_one_or_none()
        if storage_path:
            Path(storage_path).unlink(missing_ok=True)
            count_cache.clear()
        await async_db.commit()
        return storage_path is not None
