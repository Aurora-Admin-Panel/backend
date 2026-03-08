from datetime import datetime
from typing import List, Optional

import strawberry
from sqlalchemy import delete, select, update, insert, func
from sqlalchemy.orm import joinedload
from strawberry.scalars import JSON
from strawberry.types import Info

from app.db.async_session import async_db_session
from app.db.models import (
    ServiceBinding as DBServiceBinding,
    ServiceDefinition as DBServiceDefinition,
    ServerDeployment as DBServerDeployment,
    DeploymentLog as DBDeploymentLog,
    DeploymentStatusEnum,
    DeploymentActionEnum,
    DeploymentLogStatusEnum,
)
from .utils import PaginationWindow


@strawberry.type
class DeploymentLog:
    id: int
    deployment_id: int
    action: str
    status: str
    plan_json: Optional[JSON]
    output: Optional[str]
    task_id: Optional[str]
    created_by_id: Optional[int]
    created_at: datetime
    finished_at: Optional[datetime]


@strawberry.type
class ServerDeployment:
    id: int
    service_binding_id: Optional[int]
    service_id: Optional[int]
    server_id: int
    values_json: JSON
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @strawberry.field
    async def logs(self) -> List[DeploymentLog]:
        stmt = (
            select(DBDeploymentLog)
            .where(DBDeploymentLog.deployment_id == self.id)
            .order_by(DBDeploymentLog.created_at.desc())
        )
        async with async_db_session() as db:
            result = await db.execute(stmt)
        return result.scalars().all()

    @strawberry.field
    async def service_binding(self) -> Optional["ServiceBindingType"]:
        if not self.service_binding_id:
            return None
        stmt = select(DBServiceBinding).where(
            DBServiceBinding.id == self.service_binding_id
        )
        async with async_db_session() as db:
            result = await db.execute(stmt)
        return result.scalars().first()

    @strawberry.field
    async def service_title(self) -> Optional[str]:
        """Resolve service title for display, from binding or direct service."""
        sid = self.service_id
        if not sid and self.service_binding_id:
            async with async_db_session() as db:
                binding = (
                    await db.execute(
                        select(DBServiceBinding).where(
                            DBServiceBinding.id == self.service_binding_id
                        )
                    )
                ).scalars().first()
                if binding:
                    sid = binding.service_id
        if not sid:
            return None
        async with async_db_session() as db:
            service = (
                await db.execute(
                    select(DBServiceDefinition).where(DBServiceDefinition.id == sid)
                )
            ).scalars().first()
        return service.title if service else None

    @staticmethod
    async def get_server_deployment(
        info: Info, id: int
    ) -> Optional["ServerDeployment"]:
        stmt = select(DBServerDeployment).where(DBServerDeployment.id == id)
        async with async_db_session() as db:
            result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_paginated_server_deployments(
        info: Info,
        limit: int = 20,
        offset: int = 0,
        server_id: Optional[int] = None,
        service_binding_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> PaginationWindow["ServerDeployment"]:
        stmt = select(DBServerDeployment).order_by(
            DBServerDeployment.updated_at.desc()
        )
        count_stmt = select(func.count(DBServerDeployment.id))

        if server_id is not None:
            stmt = stmt.where(DBServerDeployment.server_id == server_id)
            count_stmt = count_stmt.where(
                DBServerDeployment.server_id == server_id
            )
        if service_binding_id is not None:
            stmt = stmt.where(DBServerDeployment.service_binding_id == service_binding_id)
            count_stmt = count_stmt.where(
                DBServerDeployment.service_binding_id == service_binding_id
            )
        if status is not None:
            stmt = stmt.where(DBServerDeployment.status == status)
            count_stmt = count_stmt.where(DBServerDeployment.status == status)

        stmt = stmt.offset(offset).limit(limit)
        async with async_db_session() as db:
            rows = await db.execute(stmt)
            count_res = await db.execute(count_stmt)
        return PaginationWindow(
            items=rows.scalars().all(),
            count=count_res.scalar() or 0,
        )


@strawberry.type
class ServiceBindingType:
    id: int
    file_id: int
    service_id: int
    is_default: bool
    created_at: datetime

    @strawberry.field
    async def deployments(self) -> List[ServerDeployment]:
        stmt = (
            select(DBServerDeployment)
            .where(DBServerDeployment.service_binding_id == self.id)
            .order_by(DBServerDeployment.updated_at.desc())
        )
        async with async_db_session() as db:
            result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_service_bindings(
        info: Info,
        file_id: Optional[int] = None,
        service_id: Optional[int] = None,
    ) -> List["ServiceBindingType"]:
        stmt = select(DBServiceBinding).order_by(
            DBServiceBinding.created_at.desc()
        )
        if file_id is not None:
            stmt = stmt.where(DBServiceBinding.file_id == file_id)
        if service_id is not None:
            stmt = stmt.where(DBServiceBinding.service_id == service_id)
        async with async_db_session() as db:
            result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def create_service_binding(
        info: Info,
        file_id: int,
        service_id: int,
        is_default: bool = False,
    ) -> "ServiceBindingType":
        row = DBServiceBinding(
            file_id=file_id,
            service_id=service_id,
            is_default=is_default,
        )
        async with async_db_session() as db:
            db.add(row)
            await db.commit()
            await db.refresh(row)
        return row

    @staticmethod
    async def delete_service_binding(info: Info, id: int) -> bool:
        stmt = delete(DBServiceBinding).where(DBServiceBinding.id == id)
        async with async_db_session() as db:
            result = await db.execute(stmt)
            await db.commit()
        return result.rowcount > 0


# ---------------------------------------------------------------------------
# Deployment lifecycle mutations
# ---------------------------------------------------------------------------

async def deploy_executable_resolver(
    info: Info,
    service_binding_id: int,
    server_ids: List[int],
    values: JSON,
) -> List[ServerDeployment]:
    from tasks.deployment import deploy_executable_task

    user = info.context["request"].state.user
    results = []
    pending_tasks = []

    async with async_db_session() as db:
        for server_id in server_ids:
            # Upsert ServerDeployment
            existing_stmt = select(DBServerDeployment).where(
                DBServerDeployment.service_binding_id == service_binding_id,
                DBServerDeployment.server_id == server_id,
            )
            existing = (await db.execute(existing_stmt)).scalars().first()

            if existing:
                existing.values_json = values
                existing.status = DeploymentStatusEnum.PENDING
                existing.is_active = True
                deployment = existing
            else:
                deployment = DBServerDeployment(
                    service_binding_id=service_binding_id,
                    server_id=server_id,
                    values_json=values,
                    status=DeploymentStatusEnum.PENDING,
                )
                db.add(deployment)

            await db.flush()

            log = DBDeploymentLog(
                deployment_id=deployment.id,
                action=DeploymentActionEnum.DEPLOY,
                status=DeploymentLogStatusEnum.PENDING,
                created_by_id=user.id if user else None,
            )
            db.add(log)
            await db.flush()

            pending_tasks.append((deployment.id, log.id, log))
            results.append(deployment)

        await db.commit()

        # Dispatch Huey tasks after commit so workers can see the data
        for dep_id, log_id, log in pending_tasks:
            task_result = deploy_executable_task(dep_id, log_id)
            log.task_id = task_result.id
        await db.commit()

        for dep in results:
            await db.refresh(dep)

    return results


async def deploy_service_resolver(
    info: Info,
    service_id: int,
    server_ids: List[int],
    values: JSON,
) -> List[ServerDeployment]:
    """Deploy a service directly (without a binding) to one or more servers."""
    from tasks.deployment import deploy_executable_task

    user = info.context["request"].state.user
    results = []
    pending_tasks = []

    async with async_db_session() as db:
        # Verify service exists
        service = (
            await db.execute(
                select(DBServiceDefinition).where(DBServiceDefinition.id == service_id)
            )
        ).scalars().first()
        if not service:
            raise ValueError(f"Service definition {service_id} not found")

        for server_id in server_ids:
            # Upsert ServerDeployment by (service_id, server_id)
            existing_stmt = select(DBServerDeployment).where(
                DBServerDeployment.service_id == service_id,
                DBServerDeployment.server_id == server_id,
            )
            existing = (await db.execute(existing_stmt)).scalars().first()

            if existing:
                existing.values_json = values
                existing.status = DeploymentStatusEnum.PENDING
                existing.is_active = True
                deployment = existing
            else:
                deployment = DBServerDeployment(
                    service_id=service_id,
                    server_id=server_id,
                    values_json=values,
                    status=DeploymentStatusEnum.PENDING,
                )
                db.add(deployment)

            await db.flush()

            log = DBDeploymentLog(
                deployment_id=deployment.id,
                action=DeploymentActionEnum.DEPLOY,
                status=DeploymentLogStatusEnum.PENDING,
                created_by_id=user.id if user else None,
            )
            db.add(log)
            await db.flush()

            pending_tasks.append((deployment.id, log.id, log))
            results.append(deployment)

        await db.commit()

        # Dispatch Huey tasks after commit so workers can see the data
        for dep_id, log_id, log in pending_tasks:
            task_result = deploy_executable_task(dep_id, log_id)
            log.task_id = task_result.id
        await db.commit()

        for dep in results:
            await db.refresh(dep)

    return results


async def redeploy_executable_resolver(
    info: Info,
    deployment_id: int,
    values: Optional[JSON] = None,
) -> DeploymentLog:
    from tasks.deployment import deploy_executable_task

    user = info.context["request"].state.user

    async with async_db_session() as db:
        deployment = (
            await db.execute(
                select(DBServerDeployment).where(
                    DBServerDeployment.id == deployment_id
                )
            )
        ).scalars().first()

        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")

        if values is not None:
            deployment.values_json = values

        deployment.status = DeploymentStatusEnum.PENDING

        log = DBDeploymentLog(
            deployment_id=deployment.id,
            action=DeploymentActionEnum.REDEPLOY,
            status=DeploymentLogStatusEnum.PENDING,
            created_by_id=user.id if user else None,
        )
        db.add(log)
        await db.flush()
        dep_id, log_id = deployment.id, log.id

        await db.commit()

        task_result = deploy_executable_task(dep_id, log_id)
        log.task_id = task_result.id
        await db.commit()
        await db.refresh(log)

    return log


async def stop_deployment_resolver(info: Info, deployment_id: int) -> DeploymentLog:
    from tasks.deployment import stop_deployment_task

    user = info.context["request"].state.user

    async with async_db_session() as db:
        deployment = (
            await db.execute(
                select(DBServerDeployment).where(
                    DBServerDeployment.id == deployment_id
                )
            )
        ).scalars().first()

        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")

        log = DBDeploymentLog(
            deployment_id=deployment.id,
            action=DeploymentActionEnum.STOP,
            status=DeploymentLogStatusEnum.PENDING,
            created_by_id=user.id if user else None,
        )
        db.add(log)
        await db.flush()
        dep_id, log_id = deployment.id, log.id

        await db.commit()

        task_result = stop_deployment_task(dep_id, log_id)
        log.task_id = task_result.id
        await db.commit()
        await db.refresh(log)

    return log


async def start_deployment_resolver(info: Info, deployment_id: int) -> DeploymentLog:
    from tasks.deployment import deploy_executable_task

    user = info.context["request"].state.user

    async with async_db_session() as db:
        deployment = (
            await db.execute(
                select(DBServerDeployment).where(
                    DBServerDeployment.id == deployment_id
                )
            )
        ).scalars().first()

        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")

        deployment.status = DeploymentStatusEnum.PENDING

        log = DBDeploymentLog(
            deployment_id=deployment.id,
            action=DeploymentActionEnum.START,
            status=DeploymentLogStatusEnum.PENDING,
            created_by_id=user.id if user else None,
        )
        db.add(log)
        await db.flush()
        dep_id, log_id = deployment.id, log.id

        await db.commit()

        task_result = deploy_executable_task(dep_id, log_id)
        log.task_id = task_result.id
        await db.commit()
        await db.refresh(log)

    return log


async def remove_deployment_resolver(info: Info, deployment_id: int) -> DeploymentLog:
    from tasks.deployment import remove_deployment_task

    user = info.context["request"].state.user

    async with async_db_session() as db:
        deployment = (
            await db.execute(
                select(DBServerDeployment).where(
                    DBServerDeployment.id == deployment_id
                )
            )
        ).scalars().first()

        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")

        deployment.status = DeploymentStatusEnum.REMOVING

        log = DBDeploymentLog(
            deployment_id=deployment.id,
            action=DeploymentActionEnum.REMOVE,
            status=DeploymentLogStatusEnum.PENDING,
            created_by_id=user.id if user else None,
        )
        db.add(log)
        await db.flush()
        dep_id, log_id = deployment.id, log.id

        await db.commit()

        task_result = remove_deployment_task(dep_id, log_id)
        log.task_id = task_result.id
        await db.commit()
        await db.refresh(log)

    return log
