from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

from tasks.utils.base import (
    TaskResult,
    OperationResult,
    StateResult,
    SystemResource,
)
from tasks.utils.files import FileResource, DirectoryResource
from tasks.utils.systemd import (
    SystemdServiceResource,
    ServiceRuntimeState,
    ServiceEnableState,
)
from tasks.utils.packages import PackageResource, PackageState
from tasks.utils.connection import AuroraConnection


class SystemOrchestrator:
    """
    Fluent helper that wires together many *SystemResource* objects and executes
    them in sequence.

    Example
    -------
    >>> orch = SystemOrchestrator(conn)
    >>> (
    ...     orch.ensure_file("motd", "/etc/motd", content="hello")
    ...         .ensure_package("htop", "htop", state=PackageState.PRESENT)
    ...         .ensure_service(
    ...             "nginx-runtime",
    ...             "nginx",
    ...             runtime=ServiceRuntimeState.STARTED,
    ...             enable=ServiceEnableState.ENABLED,
    ...         )
    ...         .execute()
    ... )
    """

    # ------------------------------------------------------------------#
    def __init__(
        self, connection: AuroraConnection, *, check_mode: bool = False
    ) -> None:
        self.connection = connection
        self.check_mode = check_mode
        self._tasks: List[SystemResource] = []
        self.variables: Dict[str, Any] = {}

    # ------------------------------------------------------------------#
    # internal helpers
    # ------------------------------------------------------------------#
    def _add_task(self, name: str, task: SystemResource) -> "SystemOrchestrator":
        """Set common flags and register task."""
        task.name = name
        task.check_mode = self.check_mode
        self._tasks.append(task)
        return self

    # ------------------------------------------------------------------#
    # variable store (optional feature)
    # ------------------------------------------------------------------#
    def set_variable(self, name: str, value: Any) -> "SystemOrchestrator":
        self.variables[name] = value
        return self

    # ------------------------------------------------------------------#
    # resource convenience builders
    # ------------------------------------------------------------------#
    def ensure_file(
        self,
        name: str,
        path: str | Path,
        *,
        src: Optional[str] = None,
        content: Optional[str] = None,
        mode: Optional[str] = None,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        **kwargs,
    ) -> "SystemOrchestrator":
        res = FileResource(
            path,
            self.connection,
            src=src,
            content=content,
            mode=mode,
            owner=owner,
            group=group,
            **kwargs,
        )
        return self._add_task(name, res)

    def ensure_directory(
        self,
        name: str,
        path: str | Path,
        *,
        mode: Optional[str] = None,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        recursive: bool = True,
        **kwargs,
    ) -> "SystemOrchestrator":
        res = DirectoryResource(
            path,
            self.connection,
            mode=mode,
            owner=owner,
            group=group,
            recursive=recursive,
            **kwargs,
        )
        return self._add_task(name, res)

    def ensure_service(
        self,
        name: str,
        service_name: str,
        *,
        runtime: ServiceRuntimeState = ServiceRuntimeState.STARTED,
        enable: Optional[ServiceEnableState] = None,
        daemon_reload: bool = False,
        **kwargs,
    ) -> "SystemOrchestrator":
        res = SystemdServiceResource(
            service_name,
            self.connection,
            runtime=runtime,
            enable=enable,
            daemon_reload=daemon_reload,
            **kwargs,
        )
        return self._add_task(name, res)

    def ensure_package(
        self,
        name: str,
        package_name: str,
        *,
        state: PackageState = PackageState.PRESENT,
        version: Optional[str] = None,
        update_cache: bool = False,
        **kwargs,
    ) -> "SystemOrchestrator":
        res = PackageResource(
            package_name,
            self.connection,
            state=state,
            version=version,
            update_cache=update_cache,
            **kwargs,
        )
        return self._add_task(name, res)

    def custom_task(self, name: str, task: SystemResource) -> "SystemOrchestrator":
        """Add a pre‑constructed SystemResource."""
        return self._add_task(name, task)

    # ------------------------------------------------------------------#
    # execution
    # ------------------------------------------------------------------#
    def execute(
        self,
        *,
        fail_fast: bool = False,
        progress_callback: Optional[Callable[[str, OperationResult], None]] = None,
    ) -> TaskResult:
        results: List[OperationResult] = []
        failed: List[str] = []
        any_changed = False
        all_ok = True

        for task in self._tasks:
            try:
                res = task.ensure()
            except Exception as exc:  # pragma: no cover
                res = OperationResult(
                    state=StateResult.FAILED,
                    message=f"Unhandled exception in '{task.name}': {exc}",
                    stderr=str(exc),
                )

            results.append(res)
            if progress_callback:
                progress_callback(task.name, res)

            if not res.success:
                all_ok = False
                failed.append(task.name)
                if fail_fast:
                    break

            if res.changed:
                any_changed = True

        return TaskResult(
            success=all_ok,
            changed=any_changed,
            results=results,
            failed_tasks=failed,
        )
