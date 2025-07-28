import os
import hashlib
import tempfile
from typing import Optional, Dict, Any, Union, TYPE_CHECKING
from tasks.utils.base import SystemResource, OperationResult, StateResult

if TYPE_CHECKING:
    from .connection import AuroraConnection


def get_md5_for_file(path: str) -> str:
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


class FileResource(SystemResource):
    """Ensure remote file exists with correct content and permissions"""

    def __init__(
        self,
        path: str,
        connection: "AuroraConnection",
        src: Optional[str] = None,
        content: Optional[str] = None,
        mode: Optional[str] = None,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        backup: bool = False,
        force: bool = False,
        **kwargs,
    ):
        super().__init__(path, connection, **kwargs)
        self.path = path
        self.src = src
        self.content = content
        self.mode = mode
        self.owner = owner
        self.group = group
        self.backup = backup
        self.force = force

        if not (src or content):
            raise ValueError("Either 'src' or 'content' must be specified")
        if src and content:
            raise ValueError("Cannot specify both 'src' and 'content'")

    def check_current_state(self) -> Dict[str, Any]:
        """Check current file state"""
        state = {
            "exists": self.connection.file_exists(self.path),
            "checksum": None,
            "mode": None,
            "owner": None,
            "group": None,
        }

        if state["exists"]:
            # Get file details
            parts = self.connection.run(
                f"stat -c '%a %U %G' '{self.path}' 2>/dev/null", publish=False
            )
            if len(parts) >= 3:
                state["mode"] = parts[0]
                state["owner"] = parts[1]
                state["group"] = parts[2]

            state["checksum"] = self.connection.get_file_md5sum(self.path)

        return state

    def _get_desired_checksum(self) -> str:
        """Get checksum of desired content"""
        if self.content:
            return hashlib.md5(self.content.encode()).hexdigest()
        elif self.src:
            return get_md5_for_file(self.src)
        return ""

    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        """Check if current state matches desired state"""
        if not current_state["exists"]:
            return False

        # Check content
        desired_checksum = self._get_desired_checksum()
        if desired_checksum != current_state["checksum"]:
            return False

        # Check permissions
        if self.mode and current_state["mode"] != self.mode:
            return False

        if self.owner and current_state["owner"] != self.owner:
            return False

        if self.group and current_state["group"] != self.group:
            return False

        return True

    def apply_changes(self) -> OperationResult:
        """Apply changes to reach desired state"""
        results = []

        # Backup existing file if requested
        if self.backup and self.connection.file_exists(self.path):
            backup_result = self.connection.execute(
                f"cp '{self.path}' '{self.path}.backup.$(date +%Y%m%d_%H%M%S)'"
            )
            if backup_result.failed:
                return OperationResult(
                    state=StateResult.FAILED,
                    message=f"Failed to backup file {self.path}",
                    stderr=backup_result.stdout,
                )

        # Transfer or create file
        if self.src:
            # Transfer file from local source
            try:
                self.connection.put(self.src, self.path)
            except Exception as e:
                return OperationResult(
                    state=StateResult.FAILED,
                    message=f"Failed to transfer file {self.src}",
                    stderr=str(e),
                )
            results.append("transferred")

        elif self.content:
            tmp_path = None
            try:
                # Create file with specified content
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
                    tmp_file.write(self.content)
                    tmp_path = tmp_file.name

                self.connection.put(tmp_path, self.path)
            except Exception as e:
                return OperationResult(
                    state=StateResult.FAILED,
                    message=f"Failed to create file {self.content}",
                    stderr=str(e),
                )
            finally:
                if tmp_path is not None:
                    os.unlink(tmp_path)
            results.append("created")

        # Set permissions
        if self.mode:
            chmod_result = self.connection.execute(f"chmod {self.mode} '{self.path}'")
            if chmod_result.failed:
                return OperationResult(
                    state=StateResult.FAILED,
                    message=f"Failed to set mode {self.mode} on {self.path}",
                    stderr=chmod_result.stdout,
                )
            results.append(f"mode={self.mode}")

        # Set ownership
        if self.owner or self.group:
            chown_target = ""
            if self.owner and self.group:
                chown_target = f"{self.owner}:{self.group}"
            elif self.owner:
                chown_target = self.owner
            elif self.group:
                chown_target = f":{self.group}"

            chown_result = self.connection.execute(
                f"chown {chown_target} '{self.path}'"
            )
            if chown_result.failed:
                return OperationResult(
                    state=StateResult.FAILED,
                    message=f"Failed to set ownership {chown_target} on {self.path}",
                    stderr=chown_result.stdout,
                )
            results.append(f"owner={chown_target}")

        return OperationResult(
            state=StateResult.CHANGED,
            message=f"File {self.path} updated: {', '.join(results)}",
            changed=True,
        )


# TODO
class DirectoryResource(SystemResource):
    """Ensure directory exists with correct permissions"""

    def __init__(
        self,
        path: str,
        connection: "AuroraConnection",
        mode: Optional[str] = None,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        recursive: bool = True,
        **kwargs,
    ):
        super().__init__(path, connection, **kwargs)
        self.path = path
        self.mode = mode
        self.owner = owner
        self.group = group
        self.recursive = recursive

    def check_current_state(self) -> Dict[str, Any]:
        """Check current directory state"""
        state = {
            "exists": self.connection.directory_exists(self.path),
            "mode": None,
            "owner": None,
            "group": None,
        }

        if state["exists"]:
            result = self.connection.execute(
                f"stat -c '%a %U %G' '{self.path}' 2>/dev/null"
            )
            if result.success and result.stdout.strip():
                parts = result.stdout.strip().split()
                if len(parts) >= 3:
                    state["mode"] = parts[0]
                    state["owner"] = parts[1]
                    state["group"] = parts[2]

        return state

    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        """Check if current state matches desired state"""
        if not current_state["exists"]:
            return False

        if self.mode and current_state["mode"] != self.mode:
            return False

        if self.owner and current_state["owner"] != self.owner:
            return False

        if self.group and current_state["group"] != self.group:
            return False

        return True

    def apply_changes(self) -> OperationResult:
        """Apply changes to reach desired state"""
        results = []

        # Create directory
        mkdir_cmd = f"mkdir {'--parents' if self.recursive else ''} '{self.path}'"
        mkdir_result = self.connection.execute(mkdir_cmd)
        if not mkdir_result.success:
            return OperationResult(
                state=StateResult.FAILED,
                message=f"Failed to create directory {self.path}",
                stderr=mkdir_result.stderr,
            )
        results.append("created")

        # Set permissions and ownership (similar to FileResource)
        if self.mode:
            chmod_result = self.connection.execute(f"chmod {self.mode} '{self.path}'")
            if not chmod_result.success:
                return OperationResult(
                    state=StateResult.FAILED,
                    message=f"Failed to set mode {self.mode} on {self.path}",
                    stderr=chmod_result.stderr,
                )
            results.append(f"mode={self.mode}")

        if self.owner or self.group:
            chown_target = ""
            if self.owner and self.group:
                chown_target = f"{self.owner}:{self.group}"
            elif self.owner:
                chown_target = self.owner
            elif self.group:
                chown_target = f":{self.group}"

            chown_result = self.connection.execute(
                f"chown {chown_target} '{self.path}'"
            )
            if not chown_result.success:
                return OperationResult(
                    state=StateResult.FAILED,
                    message=f"Failed to set ownership {chown_target} on {self.path}",
                    stderr=chown_result.stderr,
                )
            results.append(f"owner={chown_target}")

        return OperationResult(
            state=StateResult.CHANGED,
            message=f"Directory {self.path} updated: {', '.join(results)}",
            changed=True,
        )
