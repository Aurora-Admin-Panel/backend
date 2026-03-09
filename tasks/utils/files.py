import os
import hashlib
import tempfile
from pathlib import Path, PurePosixPath
from typing import Optional, Dict, Any, Union, TYPE_CHECKING
from loguru import logger
from tasks.utils.base import SystemResource, OperationResult, StateResult
from tasks.utils.helper import q

if TYPE_CHECKING:
    from .connection import AuroraConnection


def get_md5_for_file(path: str) -> str:
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


class FileResource(SystemResource):
    """Idempotently ensure that a *remote* file exists with the desired
    content, permissions and ownership.

    Parameters
    ----------
    path : str | pathlib.Path
        Remote absolute path to the target file.
    src : str, optional
        Local source file that will be uploaded when the remote file is
        absent or its checksum differs.
    content : str, optional
        Literal content to write to the remote file.  Mutually exclusive with
        *src*.
    create_parents : bool, default True
        When *path*'s parent directory does not exist, create it first using
        ``mkdir -p``.
    backup : bool, default False
        If *True* and the remote file already exists, create a timestamped
        ``.backup`` copy **before** applying changes.
    force : bool, default False
        Re‑upload the file even when the checksum matches.  Useful when you
        want to overwrite attributes (mode/owner) without an additional
        ``chmod``/``chown`` call.
    """

    DEFAULT_MODE = "0644"
    SCRIPT = """
P={path};
if [ -f "$P" ]; then
printf 'exists\\t1\\n';
# stat (GNU first, then BSD/macOS)
if stat -c '%a %U %G' "$P" >/dev/null 2>&1; then
    set -- $(stat -c '%a %U %G' "$P");
else
    set -- $(stat -f '%Lp %Su %Sg' "$P");
fi
printf 'mode\\t%s\\nowner\\t%s\\ngroup\\t%s\\n' "$1" "$2" "$3";

# checksum (md5sum, then md5, then openssl)
if command -v md5sum >/dev/null 2>&1; then
    C=$(md5sum "$P" | awk '{{print $1}}');
elif command -v md5 >/dev/null 2>&1; then
    C=$(md5 -q "$P");
elif command -v openssl >/dev/null 2>&1; then
    C=$(openssl md5 -r "$P" | awk '{{print $1}}');
else
    C="";
fi
printf 'checksum\\t%s\\n' "$C";
else
printf 'exists\\t0\\n';
fi
    """

    def __init__(
        self,
        path: Union[str, Path],
        connection: "AuroraConnection",
        *,
        src: Optional[str] = None,
        content: Optional[str] = None,
        mode: Optional[str] = None,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        backup: bool = False,
        force: bool = False,
        create_parents: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(str(path), connection, **kwargs)

        self.path = PurePosixPath(str(path))
        self.src = src
        self.content = content
        self.mode = mode
        self.owner = owner
        self.group = group
        self.backup = backup
        self.force = force
        self.create_parents = create_parents

        if not (src or content):
            raise ValueError("Either 'src' or 'content' must be specified")
        if src and content:
            raise ValueError("Cannot specify both 'src' and 'content'")

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    def _desired_checksum(self) -> str:
        if self.content is not None:
            return hashlib.md5(self.content.encode()).hexdigest()
        return get_md5_for_file(self.src) if self.src else ""

    def _remote_stats(self, *, refresh: bool = False) -> Dict[str, Any]:
        cache_key = "remote_file_stats"
        if not refresh and cache_key in self._facts_cache:
            return self._facts_cache[cache_key]

        state: Dict[str, Any] = {
            "exists": False,
            "checksum": None,
            "mode": None,
            "owner": None,
            "group": None,
        }

        # Single round-trip: exists + mode/owner/group + checksum
        script = self.SCRIPT.format(path=self.path).strip()

        res = self.connection.execute(f"sh -c {q(script)}")
        if not res.ok:
            # cache the "not found" state to avoid repeated checks in the same ensure()
            self._facts_cache[cache_key] = state
            return state

        out = self.connection.strip_stdout(res)
        for line in out.splitlines():
            k, _, v = line.partition("\t")
            v = v.strip()
            if k == "exists":
                state["exists"] = v == "1"
            elif k in ("mode", "owner", "group", "checksum"):
                state[k] = v or None

        self._facts_cache[cache_key] = state
        return state

    # ------------------------------------------------------------------
    # Abstract method implementations
    # ------------------------------------------------------------------
    def check_current_state(self) -> Dict[str, Any]:
        return self._remote_stats()

    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        if not current_state["exists"]:
            return False

        if not self.force:
            if self._desired_checksum() != current_state["checksum"]:
                return False

        if self.mode and current_state["mode"] != self.mode.lstrip("0"):
            return False

        if self.owner and current_state["owner"] != self.owner:
            return False

        if self.group and current_state["group"] != self.group:
            return False

        return True

    def apply_changes(self) -> OperationResult:
        changes: list[str] = []

        # Ensure parent directory exists -----------------------------------
        parent_dir = self.path.parent
        if self.create_parents and not self.connection.directory_exists(parent_dir):
            mkdir_result = self.connection.execute(f"mkdir -p {q(parent_dir)}")
            if not mkdir_result.ok:
                return OperationResult(
                    name=self.name,
                    state=StateResult.FAILED,
                    message=f"Failed to create parent directory {parent_dir}",
                    stderr=mkdir_result.stderr,
                )
            changes.append("parent_dir_created")

        # Backup existing file if requested --------------------------------
        if self.backup and self.connection.file_exists(self.path):
            backup_name = f"{self.path}.backup.$(date +%Y%m%d_%H%M%S)"
            cp_res = self.connection.execute(f"cp {q(self.path)} {q(backup_name)}")
            if cp_res.failed:
                return OperationResult(
                    name=self.name,
                    state=StateResult.FAILED,
                    message=f"Failed to create backup of {self.path}",
                    stderr=cp_res.stderr,
                )
            changes.append("backup_created")

        # Determine if upload needed ---------------------------------------
        curr_state = self._remote_stats()
        upload_needed = self.force or (
            not curr_state["exists"]
            or self._desired_checksum() != curr_state["checksum"]
        )

        if upload_needed:
            if self.src is not None:
                try:
                    tmp_remote = self.connection.mktemp()
                    self.connection.put(self.src, tmp_remote)
                    install_cmd = f"install -D -m {self.mode if self.mode else self.DEFAULT_MODE} {q(tmp_remote)} {q(self.path)}"
                    install_res = self.connection.execute(install_cmd)
                    if install_res.failed:
                        return OperationResult(
                            name=self.name,
                            state=StateResult.FAILED,
                            message=f"Failed to upload {self.src}",
                            stderr=install_res.stderr,
                        )
                    self.connection.execute(f"rm -f {q(tmp_remote)}")
                except Exception as exc:
                    return OperationResult(
                        name=self.name,
                        state=StateResult.FAILED,
                        message=f"Failed to upload {self.src}",
                        stderr=str(exc),
                    )
            else:
                tmp_local: Optional[str] = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, mode="w") as tmp:
                        tmp.write(self.content)
                        tmp_local = tmp.name
                    tmp_remote = self.connection.mktemp()
                    self.connection.put(tmp_local, tmp_remote)
                    install_cmd = f"install -D -m {self.mode if self.mode else self.DEFAULT_MODE} {q(tmp_remote)} {q(self.path)}"
                    install_res = self.connection.execute(install_cmd)
                    if install_res.failed:
                        return OperationResult(
                            name=self.name,
                            state=StateResult.FAILED,
                            message="Failed to transfer inline content",
                            stderr=install_res.stderr,
                        )
                    self.connection.execute(f"rm -f {q(tmp_remote)}")
                except Exception as exc:
                    return OperationResult(
                        name=self.name,
                        state=StateResult.FAILED,
                        message="Failed to transfer inline content",
                        stderr=str(exc),
                    )
                finally:
                    if tmp_local and os.path.exists(tmp_local):
                        os.unlink(tmp_local)
            changes.append("content_uploaded")
            self._remote_stats(refresh=True)

        # Permissions -------------------------------------------------------
        curr_state = self._remote_stats()
        if self.mode and (upload_needed or curr_state["mode"] != self.mode):
            chmod_res = self.connection.execute(f"chmod {self.mode} {q(self.path)}")
            if chmod_res.failed:
                return OperationResult(
                    name=self.name,
                    state=StateResult.FAILED,
                    message=f"Failed to set mode {self.mode} on {self.path}",
                    stderr=chmod_res.stderr,
                )
            changes.append(f"mode={self.mode}")

        # Ownership ---------------------------------------------------------
        if any([self.owner, self.group]):
            desired_target = f"{self.owner or ''}:{self.group or ''}".strip(":")
            if (
                upload_needed
                or curr_state["owner"] != self.owner
                or curr_state["group"] != self.group
            ):
                chown_res = self.connection.execute(
                    f"chown {desired_target} {q(self.path)}"
                )
                if chown_res.failed:
                    return OperationResult(
                        name=self.name,
                        state=StateResult.FAILED,
                        message=(
                            f"Failed to set ownership {desired_target} on {self.path}"
                        ),
                        stderr=chown_res.stderr,
                    )
                changes.append(f"owner={desired_target}")

        if not changes:
            return OperationResult(
                name=self.name,
                state=StateResult.SUCCESS,
                message=f"File {self.path} already in desired state",
                changed=False,
            )

        return OperationResult(
            name=self.name,
            state=StateResult.CHANGED,
            message=f"File {self.path} updated: {', '.join(changes)}",
            changed=True,
            details={"changes": changes},
        )


class DirectoryResource(SystemResource):
    """Idempotently ensure that a remote directory exists with the desired
    permissions and ownership.
    """

    def __init__(
        self,
        path: Union[str, Path],
        connection: "AuroraConnection",
        *,
        mode: Optional[str] = None,
        owner: Optional[str] = None,
        group: Optional[str] = None,
        recursive: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(str(path), connection, **kwargs)

        self.path = Path(path)
        self.mode = mode
        self.owner = owner
        self.group = group
        self.recursive = recursive

    def _remote_stats(self, *, refresh: bool = False) -> Dict[str, Any]:
        """Return cached remote directory state."""
        cache_key = "remote_dir_stats"
        if not refresh and cache_key in self._facts_cache:
            return self._facts_cache[cache_key]

        state = {
            "exists": self.connection.directory_exists(self.path),
            "mode": None,
            "owner": None,
            "group": None,
        }

        if state["exists"]:
            cmd = f"stat -c '%a %U %G' {q(self.path)}"
            output = self.connection.run(cmd, publish=False)
            parts = output.strip().split()
            if len(parts) >= 3:
                state["mode"], state["owner"], state["group"] = parts[:3]

        self._facts_cache[cache_key] = state
        return state

    # ------------------------------------------------------------------
    # Abstract method implementations
    # ------------------------------------------------------------------
    def check_current_state(self) -> Dict[str, Any]:
        return self._remote_stats()

    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        if not current_state["exists"]:
            return False

        if self.mode and current_state["mode"] != self.mode.lstrip("0"):
            return False
        if self.owner and current_state["owner"] != self.owner:
            return False
        if self.group and current_state["group"] != self.group:
            return False
        return True

    def apply_changes(self) -> OperationResult:
        changes: list[str] = []
        curr_state = self.check_current_state()

        # 1. Create directory if needed ------------------------------------
        if not curr_state["exists"]:
            mkdir_res = self.connection.execute(
                f"mkdir {'-p' if self.recursive else ''} {q(self.path)}"
            )
            if mkdir_res.failed:
                return OperationResult(
                    name=self.name,
                    state=StateResult.FAILED,
                    message=f"Failed to create directory {self.path}",
                    stderr=mkdir_res.stderr,
                )
            changes.append("created")

        # 2. Permissions ----------------------------------------------------
        if self.mode and (not curr_state["mode"] or curr_state["mode"] != self.mode):
            chmod_flags = "-R" if self.recursive else ""
            chmod_res = self.connection.execute(
                f"chmod {chmod_flags} {self.mode} {q(self.path)}".strip()
            )
            if chmod_res.failed:
                return OperationResult(
                    name=self.name,
                    state=StateResult.FAILED,
                    message=f"Failed to set mode {self.mode} on {self.path}",
                    stderr=chmod_res.stderr,
                )
            changes.append(f"mode={self.mode}")

        # 3. Ownership ------------------------------------------------------
        if any([self.owner, self.group]):
            chown_target = f"{self.owner or ''}:{self.group or ''}".strip(":")
            if (
                not curr_state["owner"]
                or not curr_state["group"]
                or curr_state["owner"] != self.owner
                or curr_state["group"] != self.group
            ):
                chown_flags = "-R" if self.recursive else ""
                chown_res = self.connection.execute(
                    f"chown {chown_flags} {chown_target} {q(self.path)}".strip()
                )
                if chown_res.failed:
                    return OperationResult(
                        name=self.name,
                        state=StateResult.FAILED,
                        message=(
                            f"Failed to set ownership {chown_target} on {self.path}"
                        ),
                        stderr=chown_res.stderr,
                    )
                changes.append(f"owner={chown_target}")

        # ------------------------------------------------------------------
        if not changes:
            return OperationResult(
                name=self.name,
                state=StateResult.SUCCESS,
                message=f"Directory {self.path} already in desired state",
                changed=False,
            )

        return OperationResult(
            name=self.name,
            state=StateResult.CHANGED,
            message=f"Directory {self.path} updated: {', '.join(changes)}",
            changed=True,
            details={"changes": changes},
        )


class TempFileResource(SystemResource):
    """Resource for creating temporary files on remote system"""

    def __init__(
        self,
        name: str,
        connection: "AuroraConnection",
        *,
        template: Optional[str] = None,
        directory: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(name, connection, **kwargs)
        self.template = template  # Template for mktemp
        self.directory = directory
        self._temp_path: Optional[str] = None

    def create_temp_file(self) -> str:
        """Create temporary file and return path"""
        cmd = "mktemp"
        if self.directory:
            cmd += " -d"
        if self.template:
            cmd += f" {self.template}"

        return self.connection.run(cmd, publish=False).strip()

    def check_current_state(self) -> Dict[str, Any]:
        """Check if temporary file/directory exists"""
        if self._temp_path is None:
            return {"exists": False, "path": None}

        exists = (
            self.connection.directory_exists(self._temp_path)
            if self.directory
            else self.connection.file_exists(self._temp_path)
        )

        return {"exists": exists, "path": self._temp_path}

    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        """Temporary files should exist once created"""
        return current_state["exists"] and current_state["path"] is not None

    def apply_changes(self) -> OperationResult:
        """Create temporary file/directory"""
        try:
            self._temp_path = self.create_temp_file()

            file_type = "directory" if self.directory else "file"
            return OperationResult(
                name=self.name,
                state=StateResult.CHANGED,
                message=f"Created temporary {file_type}: {self._temp_path}",
                changed=True,
                details={"temp_path": self._temp_path, "type": file_type},
            )
        except Exception as e:
            return OperationResult(
                name=self.name,
                state=StateResult.FAILED,
                message=f"Failed to create temporary {'directory' if self.directory else 'file'}",
                stderr=str(e),
            )

    @property
    def temp_path(self) -> Optional[str]:
        """Get the path of the created temporary file/directory"""
        return self._temp_path

    def cleanup(self) -> OperationResult:
        """Remove the temporary file/directory"""
        if self._temp_path is None:
            return OperationResult(
                name=self.name,
                state=StateResult.SUCCESS,
                message="No temporary file to clean up",
            )

        try:
            cmd = f"rm -rf '{self._temp_path}'"
            result = self.connection.execute(cmd)

            if result.ok:
                self._temp_path = None
                return OperationResult(
                    name=self.name,
                    state=StateResult.CHANGED,
                    message=f"Cleaned up temporary file: {self._temp_path}",
                    changed=True,
                )
            else:
                return OperationResult(
                    name=self.name,
                    state=StateResult.FAILED,
                    message=f"Failed to clean up temporary file: {self._temp_path}",
                    stderr=result.stderr,
                )
        except Exception as e:
            return OperationResult(
                name=self.name,
                state=StateResult.FAILED,
                message=f"Failed to clean up temporary file: {self._temp_path}",
                stderr=str(e),
            )
