from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List

from tasks.utils.base import SystemResource, OperationResult, StateResult
from tasks.utils.files import FileResource
from tasks.utils.helper import q
from tasks.utils.connection import AuroraConnection
from tasks.utils.exception import AuroraException


class ServiceRuntimeState(Enum):
    STARTED = "started"  # ensure running
    STOPPED = "stopped"  # ensure not running
    RESTARTED = "restarted"  # force restart
    RELOADED = "reloaded"  # try reload, fallback restart


class ServiceEnableState(Enum):
    ENABLED = "enabled"  # enabled at boot
    DISABLED = "disabled"  # disabled at boot
    MASKED = "masked"  # symlink → /dev/null: cannot start
    UNMASKED = "unmasked"  # ensure *not* masked (but leave enabled/disabled untouched)


class SystemdServiceResource(SystemResource):
    """
    Ensure a systemd service has the desired **runtime** and **enablement**
    state, optionally running *systemctl daemon‑reload* first.

    Example::

        SystemdServiceResource(
            "nginx",
            conn,
            runtime=ServiceRuntimeState.STARTED,
            enable=ServiceEnableState.ENABLED,
            daemon_reload=True,
        )
    """

    # -------------------- init -------------------------------------------#
    def __init__(
        self,
        name: str,
        connection: "AuroraConnection",
        *,
        runtime: ServiceRuntimeState = ServiceRuntimeState.STARTED,
        enable: Optional[ServiceEnableState] = None,
        daemon_reload: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(name, connection, **kwargs)
        self.service_name: str = name
        self.runtime_state: ServiceRuntimeState = runtime
        self.enable_state: Optional[ServiceEnableState] = enable
        self.daemon_reload: bool = daemon_reload

    # -------------------- remote stats -----------------------------------#
    def _remote_stats(self, *, refresh: bool = False) -> Dict[str, Any]:
        cache_key = f"systemd:{self.service_name}"
        if not refresh and cache_key in self._facts_cache:
            return self._facts_cache[cache_key]

        stats = {
            "active": False,
            "enabled": False,
            "masked": False,
            "sub_state": None,
        }

        # show properties for active/sub‑state
        res = self.connection.execute(
            f"systemctl show {q(self.service_name)} "
            "--property=ActiveState,SubState --no-pager"
        )
        if res.ok:
            for line in res.stdout.splitlines():
                if line.startswith("ActiveState="):
                    stats["active"] = line.split("=", 1)[1] == "active"
                elif line.startswith("SubState="):
                    stats["sub_state"] = line.split("=", 1)[1]

        # enable / mask state
        res_enabled = self.connection.execute(
            f"systemctl is-enabled {q(self.service_name)}"
        )
        if res_enabled.ok:
            out = res_enabled.stdout.strip()
            stats["enabled"] = out == "enabled"
            stats["masked"] = out == "masked"
        else:
            # 'static', 'indirect', etc. count as not-enabled / not-masked
            out = res_enabled.stdout.strip()
            stats["masked"] = out == "masked"
            stats["enabled"] = False

        self._facts_cache[cache_key] = stats
        return stats

    # -------------------- SystemResource interface -----------------------#
    def check_current_state(self) -> Dict[str, Any]:
        return self._remote_stats()

    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        # Runtime ---------------------------------------------------------
        if (
            self.runtime_state == ServiceRuntimeState.STARTED
            and not current_state["active"]
        ):
            return False
        if (
            self.runtime_state == ServiceRuntimeState.STOPPED
            and current_state["active"]
        ):
            return False
        # RESTARTED / RELOADED always considered a change
        if self.runtime_state in {
            ServiceRuntimeState.RESTARTED,
            ServiceRuntimeState.RELOADED,
        }:
            return False

        # Enablement ------------------------------------------------------
        if self.enable_state is not None:
            if self.enable_state == ServiceEnableState.ENABLED:
                return current_state["enabled"] and not current_state["masked"]
            if self.enable_state == ServiceEnableState.DISABLED:
                return (not current_state["enabled"]) and (not current_state["masked"])
            if self.enable_state == ServiceEnableState.MASKED:
                return current_state["masked"]
            if self.enable_state == ServiceEnableState.UNMASKED:
                return not current_state["masked"]

        return True  # nothing left to change

    def apply_changes(self) -> OperationResult:
        cmds: List[str] = []
        svc = q(self.service_name)

        # daemon‑reload first if requested
        if self.daemon_reload:
            cmds.append("systemctl daemon-reload")

        current = self._remote_stats()

        # ------------ enable / mask dimension ---------------------------#
        if self.enable_state == ServiceEnableState.MASKED and not current["masked"]:
            cmds.append(f"systemctl mask {svc}")
        elif self.enable_state == ServiceEnableState.UNMASKED and current["masked"]:
            cmds.append(f"systemctl unmask {svc}")
        elif self.enable_state == ServiceEnableState.ENABLED:
            # must unmask first if masked
            if current["masked"]:
                cmds.append(f"systemctl unmask {svc}")
            if not current["enabled"]:
                cmds.append(f"systemctl enable {svc}")
        elif self.enable_state == ServiceEnableState.DISABLED:
            # must unmask first if masked
            if current["masked"]:
                cmds.append(f"systemctl unmask {svc}")
            if current["enabled"]:
                cmds.append(f"systemctl disable {svc}")

        # ------------ runtime dimension ---------------------------------#
        if self.runtime_state == ServiceRuntimeState.STARTED and not current["active"]:
            cmds.append(f"systemctl start {svc}")
        elif self.runtime_state == ServiceRuntimeState.STOPPED and current["active"]:
            cmds.append(f"systemctl stop {svc}")
        elif self.runtime_state == ServiceRuntimeState.RESTARTED:
            cmds.append(f"systemctl restart {svc}")
        elif self.runtime_state == ServiceRuntimeState.RELOADED:
            cmds.append(f"systemctl reload {svc} || systemctl restart {svc}")

        # ----------------------------------------------------------------#
        executed: List[str] = []
        for cmd in cmds:
            res = self.connection.execute(cmd)
            if not res.ok:
                return OperationResult(
                    StateResult.FAILED,
                    f"Command failed: {cmd}",
                    stderr=res.stderr or res.stdout,
                    details={"executed": executed},
                )
            executed.append(cmd)
            # refresh stats cache after each successful op that can change state
            self._remote_stats(refresh=True)

        if not executed:
            return OperationResult(
                StateResult.SUCCESS,
                f"Service {self.service_name} already in desired state",
                changed=False,
            )

        return OperationResult(
            StateResult.CHANGED,
            f"Service {self.service_name}: {'; '.join(executed)}",
            changed=True,
            details={"executed": executed},
        )


class SystemdUnitFileResource(SystemResource):
    """Ensure a systemd unit file’s content and path, then daemon-reload."""

    def __init__(
        self,
        name: str,
        connection: "AuroraConnection",
        *,
        content: str,
        unit_type: str = "service",
        user_unit: bool = False,
        mode: str = "644",
        backup: bool = False,
        **kwargs,
    ) -> None:
        # Determine final unit file path first
        self.unit_filename = f"{name}.{unit_type}"
        self.unit_path = (
            Path(f"/etc/systemd/user/{self.unit_filename}")
            if user_unit
            else Path(f"/etc/systemd/system/{self.unit_filename}")
        )
        # Initialise an internal FileResource to manage the file itself
        self._file_res = FileResource(
            self.unit_path,
            connection,
            content=content,
            mode=mode,
            backup=backup,
            **kwargs,
        )
        super().__init__(str(self.unit_path), connection, **kwargs)
        self.user_unit = user_unit

    # ------------------------------------------------------------------
    # Delegation helpers
    # ------------------------------------------------------------------
    def _remote_stats(self, *, refresh: bool = False) -> Dict[str, Any]:
        # Re-use the underlying FileResource cache
        return self._file_res._remote_stats(refresh=refresh)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # SystemResource interface
    # ------------------------------------------------------------------
    def check_current_state(self) -> Dict[str, Any]:
        return self._file_res.check_current_state()

    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        return self._file_res.desired_state_matches(current_state)

    def apply_changes(self) -> OperationResult:
        file_result = self._file_res.ensure()
        if file_result.state == StateResult.FAILED:
            return file_result

        # Only reload daemon when the unit file actually changed
        if file_result.changed:
            res = self.connection.execute("systemctl daemon-reload")
            if not res.ok:
                return OperationResult(
                    StateResult.FAILED,
                    f"Failed to daemon-reload after updating {self.unit_filename}",
                    stderr=res.stderr or res.stdout,
                )
            return OperationResult(
                StateResult.CHANGED,
                f"Unit {self.unit_filename} updated and daemon reloaded",
                changed=True,
                details={"file_changes": file_result.details.get("changes", [])},
            )

        return OperationResult(
            StateResult.SUCCESS,
            f"Unit {self.unit_filename} already in desired state",
            changed=False,
        )
