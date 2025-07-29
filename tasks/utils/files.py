import os
import hashlib
import tempfile
from pathlib import Path, PurePosixPath
from typing import Optional, Dict, Any, Union, TYPE_CHECKING
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

        self.path = path.as_posix() if isinstance(path, Path) else PurePosixPath(path)
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
            "exists": self.connection.file_exists(self.path),
            "checksum": None,
            "mode": None,
            "owner": None,
            "group": None,
        }

        if state["exists"]:
            gnu_cmd = f"stat -c '%a %U %G' {q(self.path)}"
            res = self.connection.execute(gnu_cmd)
            if not res.ok:
                # Try BSD/macOS format string
                bsd_cmd = f"stat -f '%Lp %Su %Sg' {q(self.path)}"
                res = self.connection.execute(bsd_cmd)

            if res.ok:
                parts = self.connection.strip_stdout(res).split()
                if len(parts) >= 3:
                    state["mode"], state["owner"], state["group"] = parts[:3]
            state["checksum"] = self.connection.get_file_md5sum(str(self.path))

        # store even if not exists so we avoid rechecking inside same ensure()
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
                    state=StateResult.FAILED,
                    message=f"Failed to create parent directory {parent_dir}",
                    stderr=mkdir_result.stderr,
                )
            changes.append("parent_dir_created")
            # Refresh cache after structural change
            self._remote_stats(refresh=True)

        # Backup existing file if requested --------------------------------
        if self.backup and self.connection.file_exists(self.path):
            backup_name = f"{self.path}.backup.$(date +%Y%m%d_%H%M%S)"
            cp_res = self.connection.execute(f"cp {q(self.path)} {q(backup_name)}")
            if cp_res.failed:
                return OperationResult(
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
                    self.connection.put(self.src, str(self.path))
                except Exception as exc:
                    return OperationResult(
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
                    self.connection.put(tmp_local, str(self.path))
                except Exception as exc:
                    return OperationResult(
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
                        state=StateResult.FAILED,
                        message=(
                            f"Failed to set ownership {desired_target} on {self.path}"
                        ),
                        stderr=chown_res.stderr,
                    )
                changes.append(f"owner={desired_target}")

        if not changes:
            return OperationResult(
                state=StateResult.SUCCESS,
                message=f"File {self.path} already in desired state",
                changed=False,
            )

        return OperationResult(
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
                state=StateResult.SUCCESS,
                message=f"Directory {self.path} already in desired state",
                changed=False,
            )

        return OperationResult(
            state=StateResult.CHANGED,
            message=f"Directory {self.path} updated: {', '.join(changes)}",
            changed=True,
            details={"changes": changes},
        )
