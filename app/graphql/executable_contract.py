from datetime import datetime
from typing import List, Optional

import strawberry
from sqlalchemy import delete, select, update, func
from strawberry.scalars import JSON
from strawberry.types import Info

from app.db.async_session import async_db_session
from app.db.models import ExecutableContract as DBExecutableContract
from app.db.schemas.executable_contract import ExecutableContractAuthoringV1
from app.utils.executable_contract import compile_executable_contract_preview
from .utils import PaginationWindow


def _compact_schema_json(contract: ExecutableContractAuthoringV1) -> dict:
    # Store a compact authoring schema shape instead of Pydantic-expanded optional nulls.
    return contract.dict(by_alias=False, exclude_none=True)


@strawberry.type
class ExecutableContract:
    id: int
    contract_key: str
    version: int
    title: str
    description: Optional[str]
    is_builtin: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    schema_json: JSON

    @strawberry.field
    def has_source(self) -> bool:
        """Whether this contract has an exec.source config."""
        if not self.schema_json or not isinstance(self.schema_json, dict):
            return False
        return bool(self.schema_json.get("exec", {}).get("source"))

    @staticmethod
    async def get_executable_contract(
        info: Info, id: int
    ) -> Optional["ExecutableContract"]:
        stmt = select(DBExecutableContract).where(DBExecutableContract.id == id)
        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_executable_contracts(
        info: Info,
        contract_key: Optional[str] = None,
        is_active: Optional[bool] = None,
        order_by: Optional[str] = "updated_at",
    ) -> List["ExecutableContract"]:
        stmt = select(DBExecutableContract).order_by(order_by)
        if contract_key:
            stmt = stmt.where(DBExecutableContract.contract_key == contract_key)
        if is_active is not None:
            stmt = stmt.where(DBExecutableContract.is_active == is_active)
        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_paginated_executable_contracts(
        info: Info,
        limit: int = 20,
        offset: int = 0,
        contract_key: Optional[str] = None,
        is_active: Optional[bool] = None,
        order_by: Optional[str] = "updated_at",
    ) -> PaginationWindow["ExecutableContract"]:
        stmt = select(DBExecutableContract).order_by(order_by)
        count_stmt = select(func.count(DBExecutableContract.id))
        if contract_key:
            stmt = stmt.where(DBExecutableContract.contract_key == contract_key)
            count_stmt = count_stmt.where(DBExecutableContract.contract_key == contract_key)
        if is_active is not None:
            stmt = stmt.where(DBExecutableContract.is_active == is_active)
            count_stmt = count_stmt.where(DBExecutableContract.is_active == is_active)
        stmt = stmt.offset(offset).limit(limit)
        async with async_db_session() as async_db:
            rows = await async_db.execute(stmt)
            count_res = await async_db.execute(count_stmt)
        return PaginationWindow(
            items=rows.scalars().all(),
            count=count_res.scalar() or 0,
        )

    @staticmethod
    async def create_executable_contract(info: Info, schema_json: JSON) -> "ExecutableContract":
        contract = ExecutableContractAuthoringV1.parse_obj(schema_json)
        row = DBExecutableContract(
            contract_key=contract.contractKey,
            version=contract.version,
            title=contract.title,
            description=contract.description,
            schema_json=_compact_schema_json(contract),
            is_active=True,
        )
        async with async_db_session() as async_db:
            async_db.add(row)
            await async_db.commit()
            await async_db.refresh(row)
        return row

    @staticmethod
    async def update_executable_contract(
        info: Info,
        id: int,
        schema_json: JSON,
        is_active: Optional[bool] = None,
    ) -> bool:
        contract = ExecutableContractAuthoringV1.parse_obj(schema_json)
        values = {
            "contract_key": contract.contractKey,
            "version": contract.version,
            "title": contract.title,
            "description": contract.description,
            "schema_json": _compact_schema_json(contract),
        }
        if is_active is not None:
            values["is_active"] = is_active
        stmt = update(DBExecutableContract).where(DBExecutableContract.id == id).values(**values)
        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            await async_db.commit()
        return result.rowcount > 0

    @staticmethod
    async def delete_executable_contract(info: Info, id: int) -> bool:
        stmt = delete(DBExecutableContract).where(DBExecutableContract.id == id)
        async with async_db_session() as async_db:
            result = await async_db.execute(stmt)
            await async_db.commit()
        return result.rowcount > 0


async def compile_executable_contract_preview_resolver(
    info: Info,
    contract: JSON,
    values: JSON,
    context: Optional[JSON] = None,
) -> JSON:
    return compile_executable_contract_preview(contract, values, context)


async def compile_executable_contract_preview_by_id_resolver(
    info: Info,
    id: int,
    values: JSON,
    context: Optional[JSON] = None,
) -> JSON:
    stmt = select(DBExecutableContract).where(DBExecutableContract.id == id)
    async with async_db_session() as async_db:
        result = await async_db.execute(stmt)
    row = result.scalars().first()
    if not row:
        return {"ok": False, "error": f"Executable contract '{id}' not found"}
    return compile_executable_contract_preview(row.schema_json, values, context)
