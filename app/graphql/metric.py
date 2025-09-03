import typing as T
from typing import Optional, List, Dict
from dataclasses import fields
from enum import Enum
from datetime import datetime, UTC
from dateutil import parser

import strawberry
from strawberry.types import Info
from sqlalchemy import text, bindparam, String as SAString
from sqlalchemy.dialects.postgresql import ARRAY

from app.db.async_session import async_db_session


# --- Enums -------------------------------------------------
DEFAULT_INTERVAL = "1 minute"
PSEUDO_TOTAL_IFACE = "__total__"


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
class Agg(Enum):
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    LAST = "last"


def _agg_sql(agg: Agg, column: str, order_by_time: str = "time") -> str:
    """
    Map Agg -> SQL fragment for bucketed aggregation.
    We avoid extension functions except for SUM/MIN/MAX/AVG.
    'LAST' fallback: max by time within bucket (works well for counters/booleans).
    """
    if agg == Agg.AVG:
        return f"avg({column})"
    if agg == Agg.MIN:
        return f"min({column})"
    if agg == Agg.MAX:
        return f"max({column})"
    if agg == Agg.SUM:
        return f"sum({column})"
    if agg == Agg.LAST:
        # Pick the value at the latest timestamp in the bucket.
        # Works without Timescale Toolkit by using DISTINCT ON trick in a subquery;
        # here we approximate using max() over time-ordered last_value via FILTER.
        # To stay portable, we’ll use max() on a parallel coalesce that prefers later rows.
        # For booleans we can just use max(bool::int)::bool in the caller.
        # In bucketed SELECTs below, we’ll special-case LAST where needed.
        return f"max({column})"  # pragmatic fallback
    return f"avg({column})"


# --- Inputs ------------------------------------------------


@strawberry.input
class TimeRangeInput:
    start: datetime
    end: Optional[datetime] = None
    # Postgres interval literal; if None -> raw points (no bucketing).
    interval: Optional[str] = None
    # Default aggregator for value columns in bucket mode.
    agg: Agg = Agg.AVG
    # Use gapfill when you want evenly spaced points (requires time_bucket_gapfill)
    # gapfill: Optional[bool] = False


@strawberry.type
class Point:
    t: datetime
    v: Optional[float] = None


@strawberry.type
class PairPoint:
    t: datetime
    a: Optional[float]
    b: Optional[float]


@strawberry.type
class SpeedPoint:
    t: datetime
    rx: Optional[float]
    tx: Optional[float]


@strawberry.type
class ServerMetricPoint:
    time: datetime
    is_online: bool
    cpu_util_pct: Optional[float] = None
    mem_used_pct: Optional[float] = None
    fs_root_used_pct: Optional[float] = None
    swap_used_pct: Optional[float] = None
    load_1m: Optional[float] = None
    load_5m: Optional[float] = None
    load_15m: Optional[float] = None
    net_rx_bps: Optional[float] = None
    net_tx_bps: Optional[float] = None

    @staticmethod
    async def get_server_metric_series(
        info: Info, server_id: int, tr: TimeRangeInput
    ) -> List["ServerMetricPoint"]:
        print(tr)
        async with async_db_session() as async_db:
            end_query = ""
            params = {
                "server_id": server_id,
                "start": tr.start,
            }
            if tr.interval:
                agg = tr.agg
                params["interval"] = tr.interval
                if tr.end:
                    end_query = "AND time < :end"
                    params["end"] = tr.end
                sql = f"""
                    SELECT
                        time_bucket((:interval)::text::interval, time) AS bucket,
                        is_online,
                        {_agg_sql(agg, "cpu_util_pct")} AS cpu_util_pct,
                        {_agg_sql(agg, "load_1m")}      AS load_1m,
                        {_agg_sql(agg, "load_5m")}      AS load_5m,
                        {_agg_sql(agg, "load_15m")}     AS load_15m,
                        {_agg_sql(agg, "mem_used_pct")}     AS mem_used_pct,
                        {_agg_sql(agg, "fs_root_used_pct")} AS fs_root_used_pct,
                        {_agg_sql(agg, "swap_used_pct")}    AS swap_used_pct,
                        {_agg_sql(agg, "net_rx_bps")}   AS net_rx_bps,
                        {_agg_sql(agg, "net_tx_bps")}   AS net_tx_bps
                    FROM server_metric
                    WHERE server_id = :server_id
                    AND time >= :start {end_query}
                    GROUP BY bucket
                    ORDER BY bucket ASC
                """
                rows = (
                    (
                        await async_db.execute(
                            text(sql),
                            params,
                        )
                    )
                    .mappings()
                    .all()
                )
                return [
                    ServerMetricPoint(
                        time=row["bucket"],
                        is_online=row["is_online"],
                        cpu_util_pct=row["cpu_util_pct"],
                        load_1m=row["load_1m"],
                        load_5m=row["load_5m"],
                        load_15m=row["load_15m"],
                        mem_used_pct=row["mem_used_pct"],
                        fs_root_used_pct=row["fs_root_used_pct"],
                        swap_used_pct=row["swap_used_pct"],
                        net_rx_bps=row["net_rx_bps"],
                        net_tx_bps=row["net_tx_bps"],
                    )
                    for row in rows
                ]

            # Raw path (no bucketing)
            sql = f"""
                SELECT
                    time,
                    is_online,
                    cpu_util_pct,
                    load_1m, load_5m, load_15m,
                    mem_used_pct, fs_root_used_pct, swap_used_pct,
                    net_rx_bps, net_tx_bps
                FROM server_metric
                WHERE server_id = :server_id
                AND time >= :start {end_query}
                ORDER BY time ASC
            """
            rows = (
                (
                    await async_db.execute(
                        text(sql),
                        params,
                    )
                )
                .mappings()
                .all()
            )

            return [
                ServerMetricPoint(
                    time=row["time"],
                    is_online=row["is_online"],
                    cpu_util_pct=row["cpu_util_pct"],
                    load_1m=row["load_1m"],
                    load_5m=row["load_5m"],
                    load_15m=row["load_15m"],
                    mem_used_pct=row["mem_used_pct"],
                    fs_root_used_pct=row["fs_root_used_pct"],
                    swap_used_pct=row["swap_used_pct"],
                    net_rx_bps=row["net_rx_bps"],
                    net_tx_bps=row["net_tx_bps"],
                )
                for row in rows
            ]


@strawberry.type
class DiskSeries:
    mount: str
    points: List[Point]

    @staticmethod
    async def disk_usage_series(
        info: Info,
        server_id: int,
        tr: TimeRangeInput,
        mounts: Optional[List[str]] = None,  # None => all mounts
    ) -> List["DiskSeries"]:
        if tr.end is None:
            tr.end = datetime.now(UTC)
        async with async_db_session() as async_db:
            filters = ["server_id = :server_id", "time >= :start", "time < :end"]
            params = {"server_id": server_id, "start": tr.start, "end": tr.end}

            if mounts:
                filters.append("mount = ANY(:mounts)")
                params["mounts"] = mounts

            where = " AND ".join(filters)

            if tr.interval:
                sql = f"""
                    SELECT mount,
                        time_bucket((:interval)::text::interval, time) AS bucket,
                        {_agg_sql(tr.agg, "used_bytes")} AS used_bytes
                    FROM disk_usage
                    WHERE {where}
                    GROUP BY mount, bucket
                    ORDER BY mount, bucket
                """
                rows = (
                    (
                        await async_db.execute(
                            text(sql),
                            {**params, "interval": tr.interval},
                        )
                    )
                    .mappings()
                    .all()
                )
            else:
                sql = f"""
                    SELECT mount, time AS bucket, used_bytes
                    FROM disk_usage
                    WHERE {where}
                    ORDER BY mount, time
                """
                rows = (await async_db.execute(text(sql), params)).mappings().all()

            # Group rows by mount
            series_map: Dict[str, List[Point]] = {}
            for r in rows:
                series_map.setdefault(r["mount"], []).append(
                    Point(
                        t=r["bucket"],
                        v=float(r["used_bytes"])
                        if r["used_bytes"] is not None
                        else None,
                    )
                )
            return [DiskSeries(mount=m, points=pts) for m, pts in series_map.items()]


@strawberry.type
class IfaceSeries:
    iface: str
    points: List[SpeedPoint]

    @staticmethod
    async def network_speed_series(
        info: Info,
        server_id: int,
        tr: "TimeRangeInput",
        ifaces: Optional[List[str]] = None,  # <-- filter decides shape
    ) -> List["IfaceSeries"]:
        """
        Derive bps from cumulative byte counters using LAG over bucketed samples.

        Behavior:
          - ifaces provided  -> one series per iface
          - ifaces omitted   -> one total series named __total__
        """
        if tr.end is None:
            tr.end = datetime.now(UTC)
        async with async_db_session() as async_db:
            interval = (tr.interval or "1 minute").strip()

            iface_filter_sql = ""
            stmt = None
            params: Dict[str, object] = {
                "server_id": server_id,
                "start": tr.start,
                "end": tr.end,
                "interval": interval,
            }
            if ifaces:
                iface_filter_sql = "AND iface = ANY(:ifaces)"
            sql = f"""
                WITH b AS (
                    SELECT
                        time_bucket((:interval)::text::interval, time) AS bucket,
                        iface,
                        max(rx_bytes_total) AS rx_bytes_total,
                        max(tx_bytes_total) AS tx_bytes_total
                    FROM network_counter
                    WHERE server_id = :server_id
                      AND time >= :start AND time < :end
                      {iface_filter_sql}
                    GROUP BY bucket, iface
                ),
                d AS (
                    SELECT
                        iface,
                        bucket,
                        (rx_bytes_total - LAG(rx_bytes_total) OVER (PARTITION BY iface ORDER BY bucket)) AS rx_diff,
                        (tx_bytes_total - LAG(tx_bytes_total) OVER (PARTITION BY iface ORDER BY bucket)) AS tx_diff
                    FROM b
                )
                SELECT
                    iface,
                    bucket,
                    GREATEST(rx_diff, 0) / EXTRACT(EPOCH FROM ((:interval)::text::interval)) AS rx,
                    GREATEST(tx_diff, 0) / EXTRACT(EPOCH FROM ((:interval)::text::interval)) AS tx
                FROM d
                WHERE rx_diff IS NOT NULL OR tx_diff IS NOT NULL
                ORDER BY iface, bucket;
            """

            stmt = text(sql)
            if ifaces:
                # Bind list[str] as text[] to keep asyncpg happy
                stmt = stmt.bindparams(bindparam("ifaces", type_=ARRAY(SAString())))
                params["ifaces"] = ifaces

            rows = (await async_db.execute(stmt, params)).mappings().all()

            if ifaces:
                # Per-iface output
                out: Dict[str, List[SpeedPoint]] = {}
                for r in rows:
                    out.setdefault(r["iface"], []).append(
                        SpeedPoint(t=r["bucket"], rx=r["rx"], tx=r["tx"])
                    )
                return [IfaceSeries(iface=k, points=v) for k, v in out.items()]

            # Totals (sum across all ifaces per bucket)
            buckets: Dict[datetime, Dict[str, float]] = {}
            for r in rows:
                b = r["bucket"]
                agg = buckets.setdefault(b, {"rx": 0.0, "tx": 0.0})
                agg["rx"] += r["rx"] or 0.0
                agg["tx"] += r["tx"] or 0.0

            points = [
                SpeedPoint(t=b, rx=v["rx"], tx=v["tx"])
                for b, v in sorted(buckets.items(), key=lambda kv: kv[0])
            ]
            return [IfaceSeries(iface=PSEUDO_TOTAL_IFACE, points=points)]


@strawberry.type
class ServerMetricSnapshot(ServerMetricPoint):
    server_id: int

    @classmethod
    def from_dict(cls, data: dict) -> "ServerMetricSnapshot":
        allowed = {f.name for f in fields(cls)}
        pruned = {k: v for k, v in data.items() if k in allowed}

        if isinstance(data.get("time"), str):
            pruned["time"] = parser.parse(data["time"])

        return cls(**pruned)
