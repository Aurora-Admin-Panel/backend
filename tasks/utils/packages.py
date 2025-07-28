from typing import Optional, Dict, Any, List
from enum import Enum

from tasks.utils.base import SystemResource
from tasks.utils.connection import AuroraConnection


class PackageState(Enum):
    """Package states"""

    PRESENT = "present"
    ABSENT = "absent"
    LATEST = "latest"


# TODO
class PackageResource(SystemResource):
    """Manage system packages"""

    def __init__(
        self,
        name: str,
        connection: "AuroraConnection",
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

    def _detect_package_manager(self) -> str:
        """Detect the package manager on the remote system"""
        # Try to detect package manager
        managers = [
            ("apt", "which apt-get"),
            ("yum", "which yum"),
            ("dnf", "which dnf"),
            ("pacman", "which pacman"),
            ("zypper", "which zypper"),
        ]

        for manager, command in managers:
            result = self.connection.execute(command)
            if result.success:
                return manager

        return "unknown"

    def check_current_state(self) -> Dict[str, Any]:
        """Check current package state"""
        state = {"installed": False, "version": None}

        if self.package_manager == "apt":
            result = self.connection.execute(
                f"dpkg-query -W -f='${{Status}} ${{Version}}' {self.package_name} 2>/dev/null"
            )
            if result.success and "install ok installed" in result.stdout:
                state["installed"] = True
                parts = result.stdout.strip().split()
                if len(parts) >= 4:
                    state["version"] = parts[3]

        elif self.package_manager in ("yum", "dnf"):
            result = self.connection.execute(
                f"{self.package_manager} list installed {self.package_name} 2>/dev/null"
            )
            state["installed"] = result.success and self.package_name in result.stdout

        elif self.package_manager == "pacman":
            result = self.connection.execute(
                f"pacman -Q {self.package_name} 2>/dev/null"
            )
            state["installed"] = result.success
            if state["installed"] and result.stdout.strip():
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    state["version"] = parts[1]

        return state

    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        """Check if current state matches desired state"""
        if self.desired_state == PackageState.PRESENT:
            if not current_state["installed"]:
                return False
            if self.version and current_state["version"] != self.version:
                return False
