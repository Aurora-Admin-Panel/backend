import datetime as dt
import strawberry
from typing import Optional, List, AsyncGenerator, Dict
import enum
from dataclasses import fields
from enum import Enum
import typing as T
import strawberry
from datetime import datetime
from dateutil import parser

# --- Enums -------------------------------------------------


@strawberry.enum
class MetricKey(Enum):
    CPU_UTIL_PCT = "cpu_util_pct"
    MEM_USED_PCT = "mem_used_pct"
    SWAP_USED_PCT = "swap_used_pct"
    FS_ROOT_USED_PCT = "fs_root_used_pct"
    LOAD_1M = "load_1m"
    LOAD_5M = "load_5m"
    LOAD_15M = "load_15m"
    NET_RX_BPS = "net_rx_bps"
    NET_TX_BPS = "net_tx_bps"
    DISK_USED_PCT = "disk_used_pct"


@strawberry.enum
class AggFn(Enum):
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    LAST = "last"


@strawberry.enum
class FillPolicy(Enum):
    NULL = "null"  # keep gaps as null (good for offline gaps)
    LOCF = "locf"  # last observation carried forward
    ZERO = "zero"  # fill with 0


# --- Inputs ------------------------------------------------


@strawberry.input
class TimeRangeInput:
    from_: T.Optional[datetime] = strawberry.field(name="from")
    to: T.Optional[datetime] = None
    lastSeconds: T.Optional[int] = None


@strawberry.input
class DownsampleInput:
    everySeconds: int
    agg: AggFn = AggFn.AVG


@strawberry.input
class SeriesRequestInput:
    metric: MetricKey
    mount: T.Optional[str] = None
    iface: T.Optional[str] = None


@strawberry.type
class Point:
    t: datetime
    v: float


@strawberry.type
class Series:
    key: str
    metric: MetricKey
    unit: str
    points: T.List[Point]
    latest: T.Optional[float]
    min: T.Optional[float]
    max: T.Optional[float]


@strawberry.type
class DiskUsageTop:
    mount: str
    usedPct: float


@strawberry.type
class IfaceRateTop:
    iface: str
    rxBps: float
    txBps: float


@strawberry.type
class ServerMetricSnapshot:
    server_id: strawberry.ID
    time: datetime
    is_online: bool
    cpu_util_pct: Optional[float] = None
    mem_used_pct: Optional[float] = None
    swap_used_pct: Optional[float] = None
    fs_root_used_pct: Optional[float] = None
    load_1m: Optional[float] = None
    load_5m: Optional[float] = None
    load_15m: Optional[float] = None
    net_rx_bps: Optional[float] = None
    net_tx_bps: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict) -> "ServerMetricSnapshot":
        allowed = {f.name for f in fields(cls)}
        pruned = {k: v for k, v in data.items() if k in allowed}

        if isinstance(pruned.get("time"), str):
            pruned["time"] = parser.parse(pruned["time"])

        return cls(**pruned)


@strawberry.type
class ServerTileSeries:
    serverId: strawberry.ID
    series: T.List[Series]


@strawberry.type
class ServerLivePayload:
    serverId: strawberry.ID
    snapshot: ServerMetricSnapshot
    append: T.List[Series]
