from enum import Enum
from typing import Optional, Dict, Any, List

from tasks.utils.base import SystemResource, OperationResult, StateResult
from tasks.utils.files import FileResource
from tasks.utils.connection import AuroraConnection
from tasks.utils.exception import AuroraException


class ServiceState(Enum):
    """Systemd service states"""

    STARTED = "started"
    STOPPED = "stopped"
    RESTARTED = "restarted"
    RELOADED = "reloaded"


class SystemdServiceResource(SystemResource):
    """Manage systemd services"""

    def __init__(
        self,
        name: str,
        connection: "AuroraConnection",
        state: ServiceState = ServiceState.STARTED,
        enabled: Optional[bool] = None,
        daemon_reload: bool = False,
        **kwargs,
    ):
        super().__init__(name, connection, **kwargs)
        self.service_name = name
        self.desired_state = state
        self.enabled = enabled
        self.daemon_reload = daemon_reload

    def check_current_state(self) -> Dict[str, Any]:
        """Check current service state"""
        state = {
            "active": False,
            "enabled": False,
            "loaded": False,
            "status": "unknown",
        }

        # Check if service is active
        active_result = self.connection.execute(
            f"systemctl is-active {self.service_name}"
        )
        state["active"] = active_result.return_code == 0
        state["status"] = active_result.stdout.strip()

        # Check if service is enabled
        enabled_result = self.connection.execute(
            f"systemctl is-enabled {self.service_name}"
        )
        state["enabled"] = enabled_result.return_code == 0

        # Check if service is loaded
        loaded_result = self.connection.execute(
            f"systemctl status {self.service_name} --no-pager -l"
        )
        state["loaded"] = "Loaded: loaded" in loaded_result.stdout

        return state

    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        """Check if current state matches desired state"""
        # Check service state
        if self.desired_state == ServiceState.STARTED:
            if not current_state["active"]:
                return False
        elif self.desired_state == ServiceState.STOPPED:
            if current_state["active"]:
                return False

        # Check enabled state
        if self.enabled is not None:
            if current_state["enabled"] != self.enabled:
                return False

        return True

    def apply_changes(self) -> OperationResult:
        """Apply changes to reach desired state"""
        results = []

        # Daemon reload if requested
        if self.daemon_reload:
            reload_result = self.connection.execute("systemctl daemon-reload")
            if not reload_result.success:
                return OperationResult(
                    state=StateResult.FAILED,
                    message=f"Failed to reload systemd daemon",
                    stderr=reload_result.stderr,
                )
            results.append("daemon-reloaded")

        # Handle service state
        if self.desired_state == ServiceState.STARTED:
            start_result = self.connection.execute(
                f"systemctl start {self.service_name}"
            )
            if not start_result.success:
                return OperationResult(
                    state=StateResult.FAILED,
                    message=f"Failed to start service {self.service_name}",
                    stderr=start_result.stderr,
                )
            results.append("started")

        elif self.desired_state == ServiceState.STOPPED:
            stop_result = self.connection.execute(f"systemctl stop {self.service_name}")
            if not stop_result.success:
                return OperationResult(
                    state=StateResult.FAILED,
                    message=f"Failed to stop service {self.service_name}",
                    stderr=stop_result.stderr,
                )
            results.append("stopped")

        elif self.desired_state == ServiceState.RESTARTED:
            restart_result = self.connection.execute(
                f"systemctl restart {self.service_name}"
            )
            if not restart_result.success:
                return OperationResult(
                    state=StateResult.FAILED,
                    message=f"Failed to restart service {self.service_name}",
                    stderr=restart_result.stderr,
                )
            results.append("restarted")

        elif self.desired_state == ServiceState.RELOADED:
            reload_result = self.connection.execute(
                f"systemctl reload {self.service_name}"
            )
            if not reload_result.success:
                # Fallback to restart if reload fails
                restart_result = self.connection.execute(
                    f"systemctl restart {self.service_name}"
                )
                if not restart_result.success:
                    return OperationResult(
                        state=StateResult.FAILED,
                        message=f"Failed to reload/restart service {self.service_name}",
                        stderr=restart_result.stderr,
                    )
                results.append("restarted")
            else:
                results.append("reloaded")

        # Handle enabled state
        if self.enabled is not None:
            if self.enabled:
                enable_result = self.connection.execute(
                    f"systemctl enable {self.service_name}"
                )
                if not enable_result.success:
                    return OperationResult(
                        state=StateResult.FAILED,
                        message=f"Failed to enable service {self.service_name}",
                        stderr=enable_result.stderr,
                    )
                results.append("enabled")
            else:
                disable_result = self.connection.execute(
                    f"systemctl disable {self.service_name}"
                )
                if not disable_result.success:
                    return OperationResult(
                        state=StateResult.FAILED,
                        message=f"Failed to disable service {self.service_name}",
                        stderr=disable_result.stderr,
                    )
                results.append("disabled")

        return OperationResult(
            state=StateResult.CHANGED,
            message=f"Service {self.service_name} updated: {', '.join(results)}",
            changed=True,
        )


# TODO Can sub class FileResource
class SystemdUnitFileResource(FileResource):
    """Manage systemd unit files"""

    def __init__(
        self,
        name: str,
        connection: "AuroraConnection",
        content: str,
        unit_type: str = "service",
        user_unit: bool = False,
        **kwargs,
    ):
        super().__init__(name, connection, content=content, mode="644", **kwargs)
        self.unit_name = name
        self.content = content
        self.unit_type = unit_type
        self.user_unit = user_unit

        # Determine unit file path
        if user_unit:
            self.unit_path = f"/etc/systemd/user/{name}.{unit_type}"
        else:
            self.unit_path = f"/etc/systemd/system/{name}.{unit_type}"

    def check_current_state(self) -> Dict[str, Any]:
        return super().check_current_state()

    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        return super().desired_state_matches(current_state)

    def apply_changes(self) -> OperationResult:
        file_result = super().ensure()
        if not file_result.success:
            return file_result

        # Reload systemd daemon
        reload_result = self.connection.execute("systemctl daemon-reload")
        if not reload_result.success:
            return OperationResult(
                state=StateResult.FAILED,
                message=f"Failed to reload systemd daemon after updating {self.unit_name}",
                stderr=reload_result.stderr,
            )

        return OperationResult(
            state=StateResult.CHANGED,
            message=f"Unit file {self.unit_name}.{self.unit_type} updated and daemon reloaded",
            changed=True,
        )


class SystemdService:
    def __init__(self, connection: AuroraConnection, service_name: str):
        self.connection = connection
        self.service_name = service_name

    @classmethod
    def create_service(
        cls, connection: AuroraConnection, service_name: str, content: str
    ):
        conn = cls(connection, service_name)
        conn.ensure_content(content, f"/etc/systemd/system/{service_name}.service")
        conn.run("systemctl daemon-reload")
        return conn

    def enable(self, now: bool = False):
        args = []
        if now:
            args.append("--now")
        self.connection.run(f"systemctl enable {self.service_name} {args}")
        if not self.is_enabled:
            raise AuroraException("Failed to enable service")

    def start(self):
        self.connection.run(f"systemctl start {self.service_name}")
        if not self.is_active:
            raise AuroraException("Failed to start service")

    @property
    def is_active(self):
        output = self.connection.run(f"systemctl is-active {self.service_name}")
        return output == "active"

    @property
    def is_enabled(self):
        output = self.connection.run(f"systemctl is-enabled {self.service_name}")
        return output == "enabled"

    @property
    def is_failed(self):
        output = self.connection.run(f"systemctl is-failed {self.service_name}")
        return output == "failed"

    def restart(self):
        self.connection.run(f"systemctl restart {self.service_name}")

    def stop(self):
        self.connection.run(f"systemctl stop {self.service_name}")

    def status(self, lines: int = 100):
        return self.connection.run(
            f"systemctl status {self.service_name} -n {lines} --no-pager"
        )

    def show(self):
        return self.connection.run(f"systemctl show {self.service_name} --no-pager")

    def journal(self, lines: int = 100):
        return self.connection.run(
            f"journalctl -u {self.service_name} -n {lines} --no-pager"
        )

    def daemon_reload(self):
        self.connection.run("systemctl daemon-reload")
