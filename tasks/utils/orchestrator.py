from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field

from tasks.utils.base import TaskResult, OperationResult, StateResult, SystemResource
from tasks.utils.files import FileResource, DirectoryResource
from tasks.utils.systemd import SystemdServiceResource, ServiceState
from tasks.utils.packages import PackageResource, PackageState

# from tasks.utils.users import UserResource
from tasks.utils.connection import AuroraConnection


class SystemOrchestrator:
    """Orchestrates system state management tasks"""

    def __init__(self, connection: AuroraConnection, check_mode: bool = False):
        self.connection = connection
        self.check_mode = check_mode
        self.tasks: List[SystemResource] = []
        self.variables: Dict[str, Any] = {}

    def set_variable(self, name: str, value: Any) -> "SystemOrchestrator":
        """Set a variable for use in tasks"""
        self.variables[name] = value
        return self

    def ensure_file(
        self,
        name: str,
        path: str,
        src: Optional[str] = None,
        content: Optional[str] = None,
        mode: Optional[str] = None,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        **kwargs,
    ) -> "SystemOrchestrator":
        """Add file management task"""
        task = FileResource(
            path=path,
            connection=self.connection,
            src=src,
            content=content,
            mode=mode,
            owner=owner,
            group=group,
            check_mode=self.check_mode,
            **kwargs,
        )
        task.name = name
        self.tasks.append(task)
        return self

    def ensure_directory(
        self,
        name: str,
        path: str,
        mode: Optional[str] = None,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        **kwargs,
    ) -> "SystemOrchestrator":
        """Add directory management task"""
        task = DirectoryResource(
            path=path,
            connection=self.connection,
            mode=mode,
            owner=owner,
            group=group,
            check_mode=self.check_mode,
            **kwargs,
        )
        task.name = name
        self.tasks.append(task)
        return self

    def ensure_service(
        self,
        name: str,
        service_name: str,
        state: ServiceState = ServiceState.STARTED,
        enabled: Optional[bool] = None,
        **kwargs,
    ) -> "SystemOrchestrator":
        """Add service management task"""
        task = SystemdServiceResource(
            name=service_name,
            connection=self.connection,
            state=state,
            enabled=enabled,
            check_mode=self.check_mode,
            **kwargs,
        )
        task.name = name
        self.tasks.append(task)
        return self

    def ensure_package(
        self,
        name: str,
        package_name: str,
        state: PackageState = PackageState.PRESENT,
        version: Optional[str] = None,
        **kwargs,
    ) -> "SystemOrchestrator":
        """Add package management task"""
        task = PackageResource(
            name=package_name,
            connection=self.connection,
            state=state,
            version=version,
            check_mode=self.check_mode,
            **kwargs,
        )
        task.name = name
        self.tasks.append(task)
        return self

    def custom_task(self, name: str, task: SystemResource) -> "SystemOrchestrator":
        """Add custom task"""
        task.name = name
        task.check_mode = self.check_mode
        self.tasks.append(task)
        return self

    def execute(
        self,
        fail_fast: bool = False,
        progress_callback: Optional[Callable[[str, OperationResult], None]] = None,
    ) -> TaskResult:
        """Execute all tasks"""
        results = []
        failed_tasks = []
        overall_success = True
        overall_changed = False

        for task in self.tasks:
            try:
                result = task.ensure()
                results.append(result)

                if progress_callback:
                    progress_callback(task.name, result)

                if not result.success:
                    overall_success = False
                    failed_tasks.append(task.name)
                    if fail_fast:
                        break

                if result.changed:
                    overall_changed = True

            except Exception as e:
                error_result = OperationResult(
                    state=StateResult.FAILED,
                    message=f"Exception in task '{task.name}': {str(e)}",
                    stderr=str(e),
                )
                results.append(error_result)
                failed_tasks.append(task.name)
                overall_success = False

                if progress_callback:
                    progress_callback(task.name, error_result)

                if fail_fast:
                    break

        return TaskResult(
            success=overall_success,
            changed=overall_changed,
            results=results,
            failed_tasks=failed_tasks,
        )
