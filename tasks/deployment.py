import json
import shlex
import tempfile
import os
from datetime import datetime, UTC

from loguru import logger
from huey.api import Task

from app.core import config
from app.db.session import db_session
from app.db.models import (
    ServerDeployment,
    DeploymentLog,
    ServiceBinding,
    ServiceDefinition,
    DeploymentStatusEnum,
    DeploymentLogStatusEnum,
    DeploymentActionEnum,
)
from app.utils.service_definition import compile_service_preview

from .config import huey
from tasks.utils.connect import connect
from tasks.utils.orchestrator import SystemOrchestrator
from tasks.utils.exception import AuroraException
from tasks.utils.helper import q

DEPLOY_BASE_DIR = "/usr/local/aurora/deployments"


def _load_deployment(db, deployment_id: int):
    """Load deployment and resolve service/file.

    Returns (deployment, file_obj, service) where file_obj may be None
    for service-direct deploys.
    """
    deployment = db.get(ServerDeployment, deployment_id)
    if not deployment:
        raise AuroraException(f"Deployment {deployment_id} not found")

    if deployment.service_binding_id:
        # Binding-based deploy
        binding = db.get(ServiceBinding, deployment.service_binding_id)
        if not binding:
            raise AuroraException(f"Service binding {deployment.service_binding_id} not found")
        return deployment, binding.file, binding.service
    elif deployment.service_id:
        # Service-direct deploy (no binding/file needed)
        service = db.get(ServiceDefinition, deployment.service_id)
        if not service:
            raise AuroraException(f"Service definition {deployment.service_id} not found")
        return deployment, None, service
    else:
        raise AuroraException(
            f"Deployment {deployment_id} has neither service_binding_id nor service_id"
        )


def _update_log(db, log_id: int, **kwargs):
    log = db.get(DeploymentLog, log_id)
    if log:
        for k, v in kwargs.items():
            setattr(log, k, v)
        db.commit()


def _service_name(deployment_id: int) -> str:
    return f"aurora-deploy-{deployment_id}"


def _unit_content(deployment: ServerDeployment, plan: dict) -> str:
    argv = plan["argv"]
    env_lines = "".join(
        f"Environment={k}={v}\n" for k, v in (plan.get("env") or {}).items()
    )
    working_dir = plan.get("workingDir") or DEPLOY_BASE_DIR
    exec_start = shlex.join(argv)

    return f"""\
[Unit]
Description=Aurora Deployment {deployment.id}
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
WorkingDirectory={working_dir}
Restart=on-failure
RestartSec=5
{env_lines}
[Install]
WantedBy=multi-user.target
"""


@huey.task(priority=3, context=True)
def deploy_executable_task(deployment_id: int, log_id: int, task: Task):
    with db_session() as db:
        deployment, file_obj, service = _load_deployment(db, deployment_id)
        log = db.get(DeploymentLog, log_id)
        if log:
            log.task_id = task.id
            log.status = DeploymentLogStatusEnum.RUNNING
        deployment.status = DeploymentStatusEnum.DEPLOYING
        db.commit()

        values = dict(deployment.values_json or {})
        server_id = deployment.server_id
        config_json = service.config_json
        file_storage_path = file_obj.storage_path if file_obj else None
        file_name = file_obj.name if file_obj else None
        source_config = config_json.get("exec", {}).get("source") if config_json else None

    try:
        # Build compilation context
        compile_context = {"jobId": str(deployment_id)}
        with db_session() as db:
            dep = db.get(ServerDeployment, deployment_id)
            if dep and dep.port_id and dep.port:
                compile_context["port"] = dep.port.num

        # Compile the service definition
        result = compile_service_preview(
            config_json, values, compile_context
        )
        if not result.get("ok"):
            error_msg = result.get("error", "Service compilation failed")
            with db_session() as db:
                _update_log(
                    db, log_id,
                    status=DeploymentLogStatusEnum.FAILED,
                    output=error_msg,
                    finished_at=datetime.now(UTC),
                )
                dep = db.get(ServerDeployment, deployment_id)
                if dep:
                    dep.status = DeploymentStatusEnum.FAILED
                    db.commit()
            return {"error": error_msg}

        plan = result["plan"]

        # Save plan to log
        with db_session() as db:
            _update_log(db, log_id, plan_json=plan)

        with connect(server_id=server_id, task=task) as conn:
            orch = SystemOrchestrator(conn)

            # 1. Ensure deployment directory
            deploy_dir = f"{DEPLOY_BASE_DIR}/{deployment_id}"
            orch.ensure_directory("deploy-dir", deploy_dir, mode="0755")

            # 2. Acquire executable binary
            bin_path = plan["argv"][0] if plan["argv"] else None

            if source_config:
                # Source-driven acquisition
                remote_bin = f"{deploy_dir}/{bin_path.split('/')[-1]}" if bin_path else f"{deploy_dir}/binary"
                orch.ensure_binary(
                    "acquire-binary",
                    remote_bin,
                    source_config=source_config,
                    src=file_storage_path,
                )
                if bin_path:
                    plan["argv"][0] = remote_bin
            elif file_storage_path:
                # Legacy: no source config, just upload the file
                remote_bin = f"{deploy_dir}/{file_name}"
                orch.ensure_file(
                    "upload-binary",
                    remote_bin,
                    src=file_storage_path,
                    mode="0755",
                )
                if bin_path:
                    plan["argv"][0] = remote_bin

            # 3. Write config files from plan
            for i, file_spec in enumerate(plan.get("files") or []):
                file_path = file_spec.get("path")
                content = file_spec.get("content", "")
                if file_path:
                    orch.ensure_file(
                        f"config-file-{i}",
                        file_path,
                        content=content,
                    )

            # Execute all file operations
            file_result = orch.execute(fail_fast=True)
            if not file_result.success:
                failed_msg = f"File setup failed: {file_result.failed_tasks}"
                conn.publish(failed_msg)
                with db_session() as db:
                    _update_log(
                        db, log_id,
                        status=DeploymentLogStatusEnum.FAILED,
                        output=failed_msg,
                        finished_at=datetime.now(UTC),
                    )
                    dep = db.get(ServerDeployment, deployment_id)
                    if dep:
                        dep.status = DeploymentStatusEnum.FAILED
                        db.commit()
                return {"error": failed_msg}

            conn.publish("Files deployed successfully")

            # 4. Determine execution mode: service (long-running) vs one-shot
            timeout = plan.get("timeoutSeconds")
            is_service = timeout is None or timeout <= 0

            if is_service:
                # Generate and deploy systemd unit
                svc_name = _service_name(deployment_id)

                with db_session() as db:
                    dep = db.get(ServerDeployment, deployment_id)

                unit_content = _unit_content(dep, plan)

                svc_orch = SystemOrchestrator(conn)
                from tasks.utils.systemd import (
                    SystemdUnitFileResource,
                    SystemdServiceResource,
                    ServiceRuntimeState,
                    ServiceEnableState,
                )

                unit_res = SystemdUnitFileResource(
                    svc_name, conn, content=unit_content
                )
                svc_orch.custom_task(f"unit-{svc_name}", unit_res)
                svc_orch.ensure_service(
                    f"start-{svc_name}",
                    svc_name,
                    runtime=ServiceRuntimeState.RESTARTED,
                    enable=ServiceEnableState.ENABLED,
                    daemon_reload=True,
                )
                svc_result = svc_orch.execute(fail_fast=True)

                if not svc_result.success:
                    failed_msg = f"Service setup failed: {svc_result.failed_tasks}"
                    conn.publish(failed_msg)
                    with db_session() as db:
                        _update_log(
                            db, log_id,
                            status=DeploymentLogStatusEnum.FAILED,
                            output=failed_msg,
                            finished_at=datetime.now(UTC),
                        )
                        dep = db.get(ServerDeployment, deployment_id)
                        if dep:
                            dep.status = DeploymentStatusEnum.FAILED
                            db.commit()
                    return {"error": failed_msg}

                conn.publish(f"Service {svc_name} started successfully")

            else:
                # One-shot execution
                argv = plan["argv"]
                env_str = " ".join(
                    f"{k}={q(v)}" for k, v in (plan.get("env") or {}).items()
                )
                cmd = f"{env_str + ' ' if env_str else ''}{shlex.join(argv)}"

                working_dir = plan.get("workingDir")
                if working_dir:
                    cmd = f"cd {q(working_dir)} && {cmd}"

                conn.publish(f"Executing: {cmd}")
                output = conn.run(cmd)
                conn.publish(f"Output: {output}")

        # Success
        with db_session() as db:
            _update_log(
                db, log_id,
                status=DeploymentLogStatusEnum.SUCCESS,
                output="Deployment completed successfully",
                finished_at=datetime.now(UTC),
            )
            dep = db.get(ServerDeployment, deployment_id)
            if dep:
                dep.status = DeploymentStatusEnum.DEPLOYED
                db.commit()

        return {"success": True}

    except AuroraException as e:
        logger.debug(str(e))
        with db_session() as db:
            _update_log(
                db, log_id,
                status=DeploymentLogStatusEnum.FAILED,
                output=str(e),
                finished_at=datetime.now(UTC),
            )
            dep = db.get(ServerDeployment, deployment_id)
            if dep:
                dep.status = DeploymentStatusEnum.FAILED
                db.commit()
        return {"error": str(e)}
    except Exception as e:
        logger.exception(e)
        with db_session() as db:
            _update_log(
                db, log_id,
                status=DeploymentLogStatusEnum.FAILED,
                output=str(e),
                finished_at=datetime.now(UTC),
            )
            dep = db.get(ServerDeployment, deployment_id)
            if dep:
                dep.status = DeploymentStatusEnum.FAILED
                db.commit()
        return {"error": str(e)}


@huey.task(priority=3, context=True)
def stop_deployment_task(deployment_id: int, log_id: int, task: Task):
    with db_session() as db:
        deployment = db.get(ServerDeployment, deployment_id)
        if not deployment:
            return {"error": f"Deployment {deployment_id} not found"}

        log = db.get(DeploymentLog, log_id)
        if log:
            log.task_id = task.id
            log.status = DeploymentLogStatusEnum.RUNNING
        db.commit()

        server_id = deployment.server_id

    try:
        svc_name = _service_name(deployment_id)

        with connect(server_id=server_id, task=task) as conn:
            from tasks.utils.systemd import (
                SystemdServiceResource,
                ServiceRuntimeState,
            )

            orch = SystemOrchestrator(conn)
            orch.ensure_service(
                f"stop-{svc_name}",
                svc_name,
                runtime=ServiceRuntimeState.STOPPED,
            )
            result = orch.execute()

            if not result.success:
                failed_msg = f"Stop failed: {result.failed_tasks}"
                conn.publish(failed_msg)
                with db_session() as db:
                    _update_log(
                        db, log_id,
                        status=DeploymentLogStatusEnum.FAILED,
                        output=failed_msg,
                        finished_at=datetime.now(UTC),
                    )
                return {"error": failed_msg}

            conn.publish(f"Service {svc_name} stopped")

        with db_session() as db:
            _update_log(
                db, log_id,
                status=DeploymentLogStatusEnum.SUCCESS,
                output=f"Service {svc_name} stopped successfully",
                finished_at=datetime.now(UTC),
            )
            dep = db.get(ServerDeployment, deployment_id)
            if dep:
                dep.status = DeploymentStatusEnum.STOPPED
                db.commit()

        return {"success": True}

    except (AuroraException, Exception) as e:
        logger.exception(e)
        with db_session() as db:
            _update_log(
                db, log_id,
                status=DeploymentLogStatusEnum.FAILED,
                output=str(e),
                finished_at=datetime.now(UTC),
            )
        return {"error": str(e)}


@huey.task(priority=3, context=True)
def remove_deployment_task(deployment_id: int, log_id: int, task: Task):
    with db_session() as db:
        deployment = db.get(ServerDeployment, deployment_id)
        if not deployment:
            return {"error": f"Deployment {deployment_id} not found"}

        log = db.get(DeploymentLog, log_id)
        if log:
            log.task_id = task.id
            log.status = DeploymentLogStatusEnum.RUNNING
        db.commit()

        server_id = deployment.server_id

    try:
        svc_name = _service_name(deployment_id)
        deploy_dir = f"{DEPLOY_BASE_DIR}/{deployment_id}"

        with connect(server_id=server_id, task=task) as conn:
            from tasks.utils.systemd import (
                SystemdServiceResource,
                ServiceRuntimeState,
                ServiceEnableState,
            )

            # Stop and disable service
            orch = SystemOrchestrator(conn)
            orch.ensure_service(
                f"stop-{svc_name}",
                svc_name,
                runtime=ServiceRuntimeState.STOPPED,
            )
            orch.execute()

            # Remove unit file
            unit_path = f"/etc/systemd/system/{svc_name}.service"
            if conn.file_exists(unit_path):
                conn.run(f"rm -f {q(unit_path)}", publish=True)
                conn.run("systemctl daemon-reload", publish=True)

            # Remove deployment directory
            if conn.directory_exists(deploy_dir):
                conn.run(f"rm -rf {q(deploy_dir)}", publish=True)

            conn.publish(f"Deployment {deployment_id} removed")

        with db_session() as db:
            _update_log(
                db, log_id,
                status=DeploymentLogStatusEnum.SUCCESS,
                output=f"Deployment {deployment_id} removed successfully",
                finished_at=datetime.now(UTC),
            )
            dep = db.get(ServerDeployment, deployment_id)
            if dep:
                dep.status = DeploymentStatusEnum.STOPPED
                dep.is_active = False
                db.commit()

        return {"success": True}

    except (AuroraException, Exception) as e:
        logger.exception(e)
        with db_session() as db:
            _update_log(
                db, log_id,
                status=DeploymentLogStatusEnum.FAILED,
                output=str(e),
                finished_at=datetime.now(UTC),
            )
            dep = db.get(ServerDeployment, deployment_id)
            if dep:
                dep.status = DeploymentStatusEnum.FAILED
                db.commit()
        return {"error": str(e)}
