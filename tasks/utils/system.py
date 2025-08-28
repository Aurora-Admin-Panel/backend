import re
import time
from pathlib import Path, PurePosixPath
from decimal import Decimal
from typing import Dict, Any, List, Tuple, TYPE_CHECKING

from invoke.exceptions import UnexpectedExit

from tasks.utils.base import SystemResource, OperationResult, StateResult
from tasks.utils.helper import q  # your existing shell-quote helper
from tasks.utils.files import FileResource

if TYPE_CHECKING:
    from .connection import AuroraConnection


def pct(u, t):
    return 0.0 if not t else (u / float(t) * 100.0)


class SystemInfoResource(SystemResource):
    """
    Collects a complete Linux snapshot by running a persisted /bin/sh probe on the remote host.
    The probe is managed idempotently via FileResource.
    """

    PROBE_VERSION_REGEX = r"#\s+aurora-system-probe\s+v([\d\.]+)"
    PROBE_BASENAME = "system_probe.sh"
    PROBE_PATH = Path(__file__).parent.parent.parent.joinpath(
        "files", "aurora", PROBE_BASENAME
    )
    PROBE_VERSION = re.search(PROBE_VERSION_REGEX, open(PROBE_PATH, "r").read()).group(
        1
    )

    # Preferred install bases (first that works wins)
    INSTALL_BASES = (
        "/usr/local/aurora",
        "/opt/aurora/bin",
        "/etc/aurora",  # last resort
    )

    def __init__(
        self,
        name: str,
        connection: "AuroraConnection",
        *,
        mount_exclude: str | None = None,
        iface_include: str | None = None,
        iface_exclude: str | None = None,
        snapshot_ttl_sec: int = 10,
        **kwargs,
    ) -> None:
        super().__init__(name, connection, **kwargs)
        self.probe_path = PurePosixPath(next(iter(self.INSTALL_BASES))).joinpath(
            self.PROBE_BASENAME
        )
        self.mount_exclude = mount_exclude
        self.iface_include = iface_include
        self.iface_exclude = iface_exclude
        self.snapshot_ttl_sec = snapshot_ttl_sec

    def check_current_state(self) -> Dict[str, Any]:
        cache_key = "system_info_snapshot"
        cached = self._facts_cache.get(cache_key)
        if cached and (time.time() - cached.get("ts", 0)) < self.snapshot_ttl_sec:
            return cached

        self._ensure_probe_installed()

        env = ""
        if self.mount_exclude:
            env += f"MOUNT_EXCLUDE={q(self.mount_exclude)} "
        if self.iface_include:
            env += f"IFACE_INCLUDE={q(self.iface_include)} "
        if self.iface_exclude:
            env += f"IFACE_EXCLUDE={q(self.iface_exclude)} "
        try:
            out = self.connection.run(f"{env}{q(self.probe_path)}", publish=False)
            snapshot = self._parse_probe_output(out)
            self._facts_cache[cache_key] = snapshot
            return snapshot
        except Exception as e:
            return {"ts": int(time.time()), "error": str(e)}

    def desired_state_matches(self, current_state: Dict[str, Any]) -> bool:
        return False

    def apply_changes(self) -> OperationResult:
        current_state = self.check_current_state()
        if current_state.get("error"):
            return OperationResult(
                name=self.name,
                state=StateResult.FAILED,
                message=f"Failed to gather system information: {current_state['error']}",
                stderr=current_state["error"],
            )

        msg = (
            f"CPU {current_state['cpu_pct']:.1f}% | "
            f"Load {current_state['load1']:.2f}/{current_state['load5']:.2f}/{current_state['load15']:.2f} | "
            f"Mem {pct(current_state['mem_used'], current_state['mem_total']):.1f}% | "
            f"Disk {pct(current_state['root_used'], current_state['root_total']):.1f}%"
        )
        return OperationResult(
            name=self.name,
            state=StateResult.SUCCESS,
            message=f"System snapshot collected - {msg}",
            details=current_state,
        )

    def _ensure_probe_installed(self) -> None:
        script = FileResource(
            path=self.probe_path,
            connection=self.connection,
            src=self.PROBE_PATH,
            mode="0755",
            create_parents=True,
        )
        st = script.check_current_state()
        if script.desired_state_matches(st):
            return
        res = script.apply_changes()
        if res.failed:
            raise RuntimeError(f"Failed to install probe: {res.message}")

    def _parse_probe_output(self, out: str) -> Dict[str, Any]:
        os_release = None
        load1 = load5 = load15 = None
        uptime_s = None
        cpu_pct = None
        mem_total = mem_used = swap_total = swap_used = None
        disks: List[Dict[str, Any]] = []
        nics: Dict[str, Tuple[int, int]] = {}

        for raw_line in out.splitlines():
            line = raw_line.strip()
            if not line or "|" not in line:
                continue
            tag, *rest = line.split("|")
            if tag == "OS":
                os_release = "|".join(rest).strip()
            elif tag == "LOAD" and len(rest) >= 3:
                load1, load5, load15 = rest[:3]
            elif tag == "UPTIME" and rest:
                uptime_s = rest[0]
            elif tag == "CPU" and rest:
                cpu_pct = rest[0]
            elif tag == "MEM" and len(rest) >= 4:
                mem_total, mem_used, swap_total, swap_used = rest[:4]
            elif tag == "DSK" and len(rest) >= 3:
                mnt, total_b, used_b = rest[:3]
                disks.append(
                    {
                        "mount": mnt,
                        "total_bytes": int(total_b),
                        "used_bytes": int(used_b),
                    }
                )
            elif tag == "NIC" and len(rest) >= 3:
                iface, rx, tx = rest[:3]
                nics[iface] = (int(rx), int(tx))
        now = time.time()
        root_total, root_used = self._root_bytes(disks)
        ifaces, sum_rx_bps, sum_tx_bps = self._compute_net_rates(now, nics)
        ifaces.sort(key=lambda x: x["iface"])  # stable order

        return {
            "ts": int(now),
            "is_online": True,
            "os_release": os_release,
            "cpu_pct": Decimal(str(cpu_pct or 0)),
            "load1": Decimal(str(load1 or 0)),
            "load5": Decimal(str(load5 or 0)),
            "load15": Decimal(str(load15 or 0)),
            "mem_total": int(mem_total or 0),
            "mem_used": int(mem_used or 0),
            "swap_total": int(swap_total or 0),
            "swap_used": int(swap_used or 0),
            "root_total": int(root_total),
            "root_used": int(root_used),
            "net_rx_bps": int(sum_rx_bps),
            "net_tx_bps": int(sum_tx_bps),
            "disks": disks,
            "ifaces": ifaces,
            "extra": {
                "uptime_seconds": float(uptime_s or 0.0),
                "probe_version": self.PROBE_VERSION,
                "probe_path": self.probe_path.as_posix(),
                "mem_used_pct": pct(int(mem_used or 0), int(mem_total or 0)),
                "root_used_pct": pct(int(root_used or 0), int(root_total or 0)),
            },
        }

    @staticmethod
    def _root_bytes(disks: List[Dict[str, Any]]) -> Tuple[int, int]:
        for d in disks:
            if d.get("mount") == "/":
                return int(d.get("total_bytes", 0)), int(d.get("used_bytes", 0))
        if disks:
            d = max(disks, key=lambda x: int(x.get("total_bytes", 0)))
            return int(d.get("total_bytes", 0)), int(d.get("used_bytes", 0))
        return 0, 0

    def _compute_net_rates(
        self, now_ts: float, nics: Dict[str, Tuple[int, int]]
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        prev = self._facts_cache.get(
            "net_prev"
        )  # {"ts": float, "nics": {iface: (rx,tx)}}
        ifaces: List[Dict[str, Any]] = []
        sum_rx_bps = sum_tx_bps = 0

        dt = None
        if prev and "ts" in prev:
            dt = max(0.001, now_ts - float(prev["ts"]))

        for iface, (rx_bytes, tx_bytes) in nics.items():
            rx_bps = tx_bps = 0
            if dt and prev and iface in prev.get("nics", {}):
                prx, ptx = prev["nics"][iface]
                drx = rx_bytes - int(prx)
                dtx = tx_bytes - int(ptx)
                if drx < 0:
                    drx = 0
                if dtx < 0:
                    dtx = 0
                rx_bps = int(drx / dt)
                tx_bps = int(dtx / dt)
                sum_rx_bps += rx_bps
                sum_tx_bps += tx_bps
            ifaces.append(
                {
                    "iface": iface,
                    "rx_bytes": int(rx_bytes),
                    "tx_bytes": int(tx_bytes),
                    "rx_bps": int(rx_bps),
                    "tx_bps": int(tx_bps),
                }
            )

        self._facts_cache["net_prev"] = {"ts": now_ts, "nics": nics}
        return ifaces, sum_rx_bps, sum_tx_bps
