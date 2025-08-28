from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Optional

from loguru import logger

from app.db.models import ServerMetric, DiskUsage, NetworkCounter
from tasks.utils.server import ServerFacts


@dataclass
class ServerSnapshot:
    metric: ServerMetric
    disks: list[DiskUsage]
    ifaces: list[NetworkCounter]
    facts: ServerFacts
    uptime: Optional[int] = None


def _to_float(x, default=0.0):
    if x is None:
        return default
    try:
        return float(x)
    except Exception:
        return default


def _to_int(x, default=0):
    if x is None:
        return default
    try:
        return int(x)
    except Exception:
        return default


def build_metric_models(details: dict, server_id: int) -> ServerSnapshot:
    """
    Map a probe `details` dict into SQLAlchemy model instances for:
      - ServerMetric (one row)
      - DiskUsage (one row per disk)
      - NetworkCounter (one row per iface)
    """
    # Convert epoch seconds to timezone-aware UTC timestamp
    ts = details.get("ts")
    dt = datetime.fromtimestamp(int(ts), tz=UTC) if ts else datetime.now(UTC)

    # Raw values
    mem_used = _to_int(details.get("mem_used"))
    mem_total = _to_int(details.get("mem_total"))
    root_used = _to_int(details.get("root_used"))
    root_total = _to_int(details.get("root_total"))
    swap_total = _to_int(details.get("swap_total"))

    # Derived percentages (fall back to computed even if provided in extra)
    if mem_used_pct := details.get("extra", {}).get("mem_used_pct"):
        mem_used_pct = _to_float(mem_used_pct)
    else:
        mem_used_pct = 100.0 * mem_used / mem_total if mem_total > 0 else None
    if root_used_pct := details.get("extra", {}).get("root_used_pct"):
        root_used_pct = _to_float(root_used_pct)
    else:
        root_used_pct = 100.0 * root_used / root_total if root_total > 0 else None
    swap_used_pct = (
        100.0 * _to_int(details.get("swap_used")) / swap_total
        if swap_total > 0
        else None
    )

    server_metric = ServerMetric(
        time=dt,
        server_id=server_id,
        is_online=bool(details.get("is_online", False)),
        cpu_util_pct=_to_float(details.get("cpu_pct")),
        load_1m=_to_float(details.get("load1")),
        load_5m=_to_float(details.get("load5")),
        load_15m=_to_float(details.get("load15")),
        mem_used_bytes=mem_used,
        swap_used_bytes=_to_int(details.get("swap_used")),
        fs_root_used_bytes=root_used,
        mem_used_pct=mem_used_pct,
        fs_root_used_pct=root_used_pct,
        swap_used_pct=swap_used_pct,
    )

    # One row per disk
    disks = []
    for d in details.get("disks", []):
        if mount := d.get("mount"):
            disks.append(
                DiskUsage(
                    time=dt,
                    server_id=server_id,
                    mount=mount,
                    used_bytes=_to_int(d.get("used_bytes")),
                )
            )
        else:
            logger.warning("Disk metric missing mount: %s", d)

    # One row per network interface (totals/counters)
    ifaces = []
    for i in details.get("ifaces", []):
        ifaces.append(
            NetworkCounter(
                time=dt,
                server_id=server_id,
                iface=i.get("iface") or "unknown",
                rx_bytes_total=_to_int(i.get("rx_bytes")),
                tx_bytes_total=_to_int(i.get("tx_bytes")),
            )
        )

    return ServerSnapshot(
        metric=server_metric,
        disks=disks,
        ifaces=ifaces,
        facts=ServerFacts(
            mem_total=mem_total,
            swap_total=swap_total,
            root_total=root_total,
            os_release=details.get("os_release"),
            probe_version=details.get("extra", {}).get("probe_version"),
        ),
        uptime=details.get("extra", {}).get("uptime"),
    )
