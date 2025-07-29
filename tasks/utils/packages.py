from typing import Optional, Dict, Any, List
from enum import Enum

from tasks.utils.base import SystemResource, OperationResult, StateResult
from tasks.utils.connection import AuroraConnection
from tasks.utils.helper import q


class PackageState(Enum):
    """Package states"""

    PRESENT = "present"
    ABSENT = "absent"
    LATEST = "latest"


class PackageResource(SystemResource):
    """Ensure a system package is in the desired state."""

    def __init__(
        self,
        name: str,
        connection: "AuroraConnection",
        *,
        state: PackageState = PackageState.PRESENT,
        version: Optional[str] = None,
        update_cache: bool = False,
        **kwargs,
    ):
        super().__init__(name, connection, **kwargs)

        self.package_name = name
        self.desired_state = state
        self.version = version
        self.update_cache = update_cache
        self.package_manager = self._detect_package_manager()

    # ------------------------------------------------------------------#
    # Helper utilities
    # ------------------------------------------------------------------#
    def _detect_package_manager(self) -> str:
        """Detect and cache the package manager on the remote host."""
        if "pkg_manager" in self._facts_cache:
            return self._facts_cache["pkg_manager"]

        managers = [
            ("apt", "bash -c 'command -v apt-get'"),
            ("yum", "bash -c 'command -v yum'"),
            ("dnf", "bash -c 'command -v dnf'"),
            ("pacman", "bash -c 'command -v pacman'"),
        ]
        for mgr, probe in managers:
            if self.connection.execute(probe).ok:
                self._facts_cache["pkg_manager"] = mgr
                return mgr

        self._facts_cache["pkg_manager"] = "unknown"
        return "unknown"

    def _cache_update_cmd(self) -> Optional[str]:
        if not self.update_cache:
            return None
        if self.package_manager == "apt":
            return "apt-get -qq update"
        if self.package_manager in {"yum", "dnf"}:
            return f"{self.package_manager} -q makecache"
        if self.package_manager == "pacman":
            return "pacman -Sy --noconfirm"
        return None

    # ------------------------------------------------------------------#
    # SystemResource overrides
    # ------------------------------------------------------------------#
    def check_current_state(self) -> Dict[str, Any]:
        state = {"installed": False, "version": None}

        if self.package_manager == "apt":
            res = self.connection.execute(
                f"dpkg-query -W -f='${{Status}} ${{Version}}' {q(self.package_name)}"
            )
            if res.ok and "install ok installed" in res.stdout:
                state["installed"] = True
                tokens = self.connection.strip_stdout(res).split()
                if len(tokens) >= 4:
                    state["version"] = tokens[3]

        elif self.package_manager in {"yum", "dnf"}:
            res = self.connection.execute(
                f"{self.package_manager} -q list installed {q(self.package_name)}"
            )
            state["installed"] = res.ok and self.package_name in res.stdout

        elif self.package_manager == "pacman":
            res = self.connection.execute(f"pacman -Q {q(self.package_name)}")
            if res.ok:
                state["installed"] = True
                tokens = res.stdout.strip().split()
                if len(tokens) >= 2:
                    state["version"] = tokens[1]

        return state

    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        if self.desired_state == PackageState.ABSENT:
            return not current_state["installed"]

        if self.desired_state == PackageState.PRESENT:
            if not current_state["installed"]:
                return False
            if self.version and current_state["version"] != self.version:
                return False
            return True

        # For LATEST we always trigger an upgrade attempt; the pkg manager
        # itself will decide whether anything changes.
        return False

    def apply_changes(self) -> OperationResult:
        if self.package_manager == "unknown":
            return OperationResult(
                state=StateResult.FAILED,
                message="Unsupported/undetected package manager",
                changed=False,
            )

        cmds: List[str] = []
        cache_cmd = self._cache_update_cmd()
        if cache_cmd:
            cmds.append(cache_cmd)

        pm = self.package_manager
        pkg = q(self.package_name)

        if self.desired_state == PackageState.ABSENT:
            if pm == "apt":
                cmds.append(f"apt-get -y -qq remove {pkg}")
            elif pm in {"yum", "dnf"}:
                cmds.append(f"{pm} -y -q remove {pkg}")
            elif pm == "pacman":
                cmds.append(f"pacman -R --noconfirm {pkg}")

        elif self.desired_state == PackageState.LATEST:
            if pm == "apt":
                cmds.append(f"apt-get -y -qq install --only-upgrade {pkg}")
            elif pm in {"yum", "dnf"}:
                cmds.append(f"{pm} -y -q update {pkg}")
            elif pm == "pacman":
                cmds.append(f"pacman -S --noconfirm {pkg}")

        elif self.desired_state == PackageState.PRESENT:
            if pm == "apt":
                if self.version:
                    cmds.append(f"apt-get -y -qq install {pkg}={q(self.version)}")
                else:
                    cmds.append(f"apt-get -y -qq install {pkg}")
            elif pm in {"yum", "dnf"}:
                if self.version:
                    cmds.append(f"{pm} -y -q install {pkg}-{q(self.version)}")
                else:
                    cmds.append(f"{pm} -y -q install {pkg}")
            elif pm == "pacman":
                cmds.append(f"pacman -S --noconfirm {pkg}")

        # Execute all commands in order, stop on failure
        executed: List[str] = []
        for cmd in cmds:
            res = self.connection.execute(cmd)
            if not res.ok:
                return OperationResult(
                    state=StateResult.FAILED,
                    message=f"Command failed: {cmd}",
                    stderr=self.connection.strip_stdout(res),
                    details={"executed": executed},
                )
            executed.append(cmd)

        return OperationResult(
            state=StateResult.CHANGED if executed else StateResult.SUCCESS,
            message=f"Package '{self.package_name}' actions: {', '.join(executed)}",
            changed=bool(executed),
            details={"executed": executed},
        )
