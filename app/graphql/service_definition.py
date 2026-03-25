from datetime import datetime
from typing import List, Optional

import strawberry
from sqlalchemy import delete, select, update, func
from strawberry.scalars import JSON
from strawberry.types import Info

from app.db.async_session import async_db_session
from app.db.models import ServiceDefinition as DBServiceDefinition
from app.db.schemas.service_definition import ServiceDefinitionAuthoringV1
from app.utils.service_definition import compile_service_preview
from .utils import PaginationWindow


def _compact_config_json(service: ServiceDefinitionAuthoringV1) -> dict:
    # Store a compact authoring schema shape instead of Pydantic-expanded optional nulls.
    return service.dict(by_alias=False, exclude_none=True)


@strawberry.type
class ServiceDefinitionType:
    id: int
    service_key: str
    version: int
    title: str
    description: Optional[str]
    is_builtin: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    config_json: JSON

    @strawberry.field
    def has_source(self) -> bool:
        """Whether this service has an exec.source config."""
        if not self.config_json or not isinstance(self.config_json, dict):
            return False
        return bool(self.config_json.get("exec", {}).get("source"))

    @staticmethod
    async def get_service_definition(
        info: Info, id: int
    ) -> Optional["ServiceDefinitionType"]:
        stmt = select(DBServiceDefinition).where(DBServiceDefinition.id == id)
        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_service_definitions(
        info: Info,
        service_key: Optional[str] = None,
        is_active: Optional[bool] = None,
        order_by: Optional[str] = "updated_at",
    ) -> List["ServiceDefinitionType"]:
        stmt = select(DBServiceDefinition).order_by(order_by)
        if service_key:
            stmt = stmt.where(DBServiceDefinition.service_key == service_key)
        if is_active is not None:
            stmt = stmt.where(DBServiceDefinition.is_active == is_active)
        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_paginated_service_definitions(
        info: Info,
        limit: int = 20,
        offset: int = 0,
        service_key: Optional[str] = None,
        is_active: Optional[bool] = None,
        order_by: Optional[str] = "updated_at",
    ) -> PaginationWindow["ServiceDefinitionType"]:
        stmt = select(DBServiceDefinition).order_by(order_by)
        count_stmt = select(func.count(DBServiceDefinition.id))
        if service_key:
            stmt = stmt.where(DBServiceDefinition.service_key == service_key)
            count_stmt = count_stmt.where(DBServiceDefinition.service_key == service_key)
        if is_active is not None:
            stmt = stmt.where(DBServiceDefinition.is_active == is_active)
            count_stmt = count_stmt.where(DBServiceDefinition.is_active == is_active)
        stmt = stmt.offset(offset).limit(limit)
        async with async_db_session() as async_db:
            rows = await async_db.execute(stmt)
            count_res = await async_db.execute(count_stmt)
        return PaginationWindow(
            items=rows.scalars().all(),
            count=count_res.scalar() or 0,
        )

    @staticmethod
    async def create_service_definition(info: Info, config_json: JSON) -> "ServiceDefinitionType":
        service = ServiceDefinitionAuthoringV1.parse_obj(config_json)
        row = DBServiceDefinition(
            service_key=service.contractKey,
            version=service.version,
            title=service.title,
            description=service.description,
            config_json=_compact_config_json(service),
            is_active=True,
        )
        async with async_db_session() as async_db:
            async_db.add(row)
            await async_db.commit()
            await async_db.refresh(row)
        return row

    @staticmethod
    async def update_service_definition(
        info: Info,
        id: int,
        config_json: JSON,
        is_active: Optional[bool] = None,
    ) -> bool:
        service = ServiceDefinitionAuthoringV1.parse_obj(config_json)
        values = {
            "service_key": service.contractKey,
            "version": service.version,
            "title": service.title,
            "description": service.description,
            "config_json": _compact_config_json(service),
        }
        if is_active is not None:
            values["is_active"] = is_active
        stmt = update(DBServiceDefinition).where(DBServiceDefinition.id == id).values(**values)
        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def delete_service_definition(info: Info, id: int) -> bool:
        stmt = delete(DBServiceDefinition).where(DBServiceDefinition.id == id)
        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            await async_db.commit()
        return result.rowcount > 0


async def compile_service_preview_resolver(
    info: Info,
    contract: JSON,
    values: JSON,
    context: Optional[JSON] = None,
) -> JSON:
    return compile_service_preview(contract, values, context)


async def compile_service_preview_by_id_resolver(
    info: Info,
    id: int,
    values: JSON,
    context: Optional[JSON] = None,
) -> JSON:
    stmt = select(DBServiceDefinition).where(DBServiceDefinition.id == id)
    async with async_db_session() as async_db:
        result = await async_db.execute(stmt)
    row = result.scalars().first()
    if not row:
        return {"ok": False, "error": f"Service definition '{id}' not found"}
    return compile_service_preview(row.config_json, values, context)
