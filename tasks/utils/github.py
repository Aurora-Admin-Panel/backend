import fnmatch
from typing import Dict, Any, Optional, TYPE_CHECKING

import requests
from loguru import logger

from tasks.utils.base import SystemResource, OperationResult, StateResult
from tasks.utils.download import RemoteDownloadResource
from tasks.utils.helper import q

if TYPE_CHECKING:
    from .connection import AuroraConnection


class GitHubReleaseResource(SystemResource):
    """Resolve a binary from GitHub releases, then download it.

    Resolves the correct download URL from the GitHub releases API on the
    control server, then delegates the actual download to a
    RemoteDownloadResource on the remote server.
    """

    ARCH_MAP = {"x86_64": "amd64", "aarch64": "arm64", "armv7l": "armv7"}

    def __init__(
        self,
        name: str,
        connection: "AuroraConnection",
        *,
        repo: str,
        asset_pattern: str,
        dest: str,
        tag: Optional[str] = None,
        extract_path: Optional[str] = None,
        strip: int = 0,
        mode: str = "0755",
        **kwargs,
    ) -> None:
        super().__init__(name, connection, **kwargs)
        self.repo = repo
        self.asset_pattern = asset_pattern
        self.dest = dest
        self.tag = tag
        self.extract_path = extract_path
        self.strip = strip
        self.mode = mode

    def _resolve_download_url(self) -> str:
        # Detect remote architecture
        arch = self.connection.run("uname -m", publish=False).strip()
        mapped_arch = self.ARCH_MAP.get(arch, arch)
        resolved_pattern = self.asset_pattern.replace("{arch}", mapped_arch)

        # Call GitHub API from control server
        if self.tag:
            api_url = f"https://api.github.com/repos/{self.repo}/releases/tags/{self.tag}"
        else:
            api_url = f"https://api.github.com/repos/{self.repo}/releases/latest"

        self.connection.publish(
            f"Resolving GitHub release: {self.repo} (pattern: {resolved_pattern})"
        )

        resp = requests.get(api_url, timeout=30, headers={"Accept": "application/vnd.github.v3+json"})
        resp.raise_for_status()
        release = resp.json()

        # Match asset name against pattern
        for asset in release.get("assets", []):
            if fnmatch.fnmatch(asset["name"], resolved_pattern):
                self.connection.publish(f"Matched asset: {asset['name']}")
                return asset["browser_download_url"]

        available = [a["name"] for a in release.get("assets", [])]
        raise RuntimeError(
            f"No asset matching '{resolved_pattern}' in {self.repo} release "
            f"{release.get('tag_name', '?')}. Available: {available}"
        )

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
        url = self._resolve_download_url()
        downloader = RemoteDownloadResource(
            f"{self.name}-download",
            self.connection,
            url=url,
            dest=self.dest,
            extract_path=self.extract_path,
            strip=self.strip,
            mode=self.mode,
        )
        return downloader.apply_changes()
