from typing import Dict, Any, Optional, TYPE_CHECKING

from loguru import logger

from tasks.utils.base import SystemResource, OperationResult, StateResult
from tasks.utils.helper import q

if TYPE_CHECKING:
    from .connection import AuroraConnection


class RemoteDownloadResource(SystemResource):
    """Download a file from a URL on the remote server and install it to a target path.

    Handles downloading via curl, archive detection and extraction (tar.gz, zip,
    raw binary), atomic installation via ``install -m MODE``, and cleanup of temp
    files.
    """

    def __init__(
        self,
        name: str,
        connection: "AuroraConnection",
        *,
        url: str,
        dest: str,
        mode: str = "0755",
        extract_path: Optional[str] = None,
        strip: int = 0,
        **kwargs,
    ) -> None:
        super().__init__(name, connection, **kwargs)
        self.url = url
        self.dest = dest
        self.mode = mode
        self.extract_path = extract_path
        self.strip = strip

    def check_current_state(self) -> Dict[str, Any]:
        script = (
            f'P={q(self.dest)}; '
            f'if [ -f "$P" ] && [ -x "$P" ]; then echo exists; '
            f'else echo missing; fi'
        )
        out = self.connection.run(f"sh -c {q(script)}", publish=False).strip()
        return {"exists": out == "exists"}

    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        return current_state["exists"]

    def apply_changes(self) -> OperationResult:
        conn = self.connection

        conn.publish(f"Downloading {self.url} ...")

        # 1. Download to temp file
        tmp = conn.run("mktemp", publish=False).strip()
        dl_cmd = (
            f"curl -fsSL --connect-timeout 30 --max-time 600 "
            f"-o {q(tmp)} {q(self.url)}"
        )
        dl_res = conn.execute(dl_cmd)
        if dl_res.failed:
            conn.run(f"rm -f {q(tmp)}", publish=False)
            return OperationResult(
                name=self.name,
                state=StateResult.FAILED,
                message=f"Download failed: {self.url}",
                stderr=conn.strip_stdout(dl_res) if hasattr(dl_res, 'stdout') else str(dl_res),
            )

        # 2. Detect file type (no `file` command needed — not on all minimal images)
        file_type = self._detect_file_type(conn, tmp)

        try:
            # Ensure parent directory exists
            from pathlib import PurePosixPath
            parent = str(PurePosixPath(self.dest).parent)
            conn.run(f"mkdir -p {q(parent)}", publish=False)

            if file_type in ("gzip", "xz", "bzip2", "tar"):
                self._extract_tar(conn, tmp)
            elif file_type == "zip":
                self._extract_zip(conn, tmp)
            else:
                # Raw binary
                conn.run(
                    f"install -m {self.mode} {q(tmp)} {q(self.dest)}",
                    publish=False,
                )
        finally:
            conn.run(f"rm -f {q(tmp)}", publish=False)

        conn.publish(f"Installed to {self.dest}")

        return OperationResult(
            name=self.name,
            state=StateResult.CHANGED,
            message=f"Downloaded and installed {self.url} to {self.dest}",
            changed=True,
            details={"url": self.url, "dest": self.dest},
        )

    def _detect_file_type(self, conn, tmp: str) -> str:
        """Detect file type via URL extension, falling back to magic bytes (od)."""
        url_path = self.url.lower().split("?")[0].split("#")[0].rstrip("/")
        if url_path.endswith((".tar.gz", ".tgz")):
            return "gzip"
        if url_path.endswith((".tar.xz", ".txz")):
            return "xz"
        if url_path.endswith((".tar.bz2", ".tbz2")):
            return "bzip2"
        if url_path.endswith(".tar"):
            return "tar"
        if url_path.endswith(".zip"):
            return "zip"

        # Read first 6 bytes as hex via od (coreutils — always available)
        hdr = conn.run(
            f"od -A n -t x1 -N 6 {q(tmp)} | tr -d ' \\n'",
            publish=False,
        ).strip().lower()
        if hdr.startswith("1f8b"):
            return "gzip"
        if hdr.startswith("504b0304"):
            return "zip"
        if hdr.startswith("fd377a585a00"):
            return "xz"
        if hdr.startswith("425a"):
            return "bzip2"
        return "binary"

    def _extract_tar(self, conn, tmp: str) -> None:
        extract_dir = conn.run("mktemp -d", publish=False).strip()
        try:
            strip_flag = f"--strip-components={self.strip}" if self.strip else ""
            conn.run(
                f"tar xf {q(tmp)} -C {q(extract_dir)} {strip_flag}",
                publish=False,
            )
            source = self._resolve_source(conn, extract_dir)
            conn.run(
                f"install -m {self.mode} {q(source)} {q(self.dest)}",
                publish=False,
            )
        finally:
            conn.run(f"rm -rf {q(extract_dir)}", publish=False)

    def _extract_zip(self, conn, tmp: str) -> None:
        extract_dir = conn.run("mktemp -d", publish=False).strip()
        try:
            conn.run(
                f"unzip -o {q(tmp)} -d {q(extract_dir)}",
                publish=False,
            )
            source = self._resolve_source(conn, extract_dir)
            conn.run(
                f"install -m {self.mode} {q(source)} {q(self.dest)}",
                publish=False,
            )
        finally:
            conn.run(f"rm -rf {q(extract_dir)}", publish=False)

    def _resolve_source(self, conn, extract_dir: str) -> str:
        if self.extract_path:
            return f"{extract_dir}/{self.extract_path}"
        # Auto-detect: find single executable or single file
        files = conn.run(
            f"find {q(extract_dir)} -type f -maxdepth 2",
            publish=False,
        ).strip().splitlines()
        if len(files) == 1:
            return files[0]
        # Try to find an executable
        executables = conn.run(
            f"find {q(extract_dir)} -type f -executable -maxdepth 2",
            publish=False,
        ).strip().splitlines()
        if len(executables) == 1:
            return executables[0]
        # Fall back to the basename of dest
        from pathlib import PurePosixPath
        basename = PurePosixPath(self.dest).name
        for f in files:
            if PurePosixPath(f).name == basename:
                return f
        raise RuntimeError(
            f"Cannot auto-detect binary in archive. "
            f"Set extract_path explicitly. Files found: {files}"
        )
