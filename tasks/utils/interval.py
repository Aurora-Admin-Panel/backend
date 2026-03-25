import random
from typing import List, Optional
from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional, Union

from app.core.config import (
    SERVER_USAGE_MAX_INTERVAL_SECONDS,
)

SERVER_USAGE_BASE_INTERVAL_SECONDS = 60
EXPONENTIAL_BACKOFF_FACTOR = 2

Number = Union[int, float, Decimal]


def should_schedule_seconds(interval_seconds: int) -> List[int]:
    now = datetime.now(UTC).timestamp()
    remaining = interval_seconds - (now % interval_seconds)
    result = []
    while remaining < 60:
        result.append(remaining)
        remaining += interval_seconds
    return result


def compute_exponential_backoff(
    last_connect: Optional[datetime],
    base_interval: int = SERVER_USAGE_BASE_INTERVAL_SECONDS,  # Starting retry interval in seconds
    factor: int = EXPONENTIAL_BACKOFF_FACTOR,  # Exponential growth factor
    max_interval: int = SERVER_USAGE_MAX_INTERVAL_SECONDS,  # Maximum interval to avoid unbounded delay (1 hour here)
) -> int:
    """
    Returns a delay (in seconds) for the next schedule attempt, using
    a simple exponential backoff approach.

    - If last_connect is None, we return the base interval.
    - Otherwise, we look at how many seconds have passed since last_connect.
      The longer it has been, the more we increase the interval.

    For example, if base=10, factor=2, and last_connect was 90 seconds ago,
    the logic might produce 20 or 40 seconds as the new delay (depending on
    how you structure the growth). This is just one example formula—tweak as needed.
    """
    # If we've never connected successfully, return the max interval right away
    if not last_connect:
        return max_interval
    last_connect = last_connect.replace(tzinfo=UTC)

    now = datetime.now(UTC)
    elapsed = (now - last_connect).total_seconds()

    delay = base_interval
    while delay < elapsed:
        delay *= factor
        if delay > max_interval:
            delay = max_interval
            break

    return int(delay)


def _pct_to_fraction(p: Union[int, float, str]) -> float:
    """
    Accepts 0.1, 10, or "10%" and returns fraction 0.1.
    """
    if isinstance(p, str):
        p = p.strip()
        if p.endswith("%"):
            return float(p[:-1]) / 100.0
        return float(p)
    p = float(p)
    return p / 100.0 if p > 1 else p


def jitter(
    value: Number,
    percent: Union[int, float, str],
    *,
    mode: str = "range",  # "range" => uniform in [-x%, +x%]; "exact" => exactly ±x%
    rng: Optional[random.Random] = None,
    min_value: Optional[Number] = None,
    max_value: Optional[Number] = None,
    round_to: Optional[Number] = None,  # e.g. 0.01 to round to cents
) -> Number:
    """
    Return `value` randomly adjusted by +/- `percent`.

    percent can be:
      - fraction: 0.1  -> 10%
      - integer:  10   -> 10%
      - string:   "10%"

    mode:
      - "range": factor = 1 + U(-p, +p)
      - "exact": factor = 1 ± p (coin flip)

    Preserves Decimal if `value` is Decimal.
    """
    p = _pct_to_fraction(percent)
    if p < 0:
        raise ValueError("percent must be >= 0")

    r = (rng or random).random()
    if mode == "exact":
        delta = p if r < 0.5 else -p
    elif mode == "range":
        delta = (r * 2 - 1) * p
    else:
        raise ValueError("mode must be 'range' or 'exact'")

    # Compute with matching numeric type
    if isinstance(value, Decimal):
        factor = Decimal(1) + (Decimal(delta))
        out = value * factor
    else:
        out = value * (1 + delta)

    # Clamp if requested
    if min_value is not None and out < min_value:
        out = min_value
    if max_value is not None and out > max_value:
        out = max_value

    # Optional rounding to a step
    if round_to is not None:
        if isinstance(out, Decimal) or isinstance(round_to, Decimal):
            step = Decimal(round_to)
            out = (out / step).to_integral_value(
                rounding=Decimal().as_tuple().exponent
            ) * step
        else:
            step = float(round_to)
            out = round(out / step) * step

    # Keep ints as ints if no fractional part
    if isinstance(value, int) and not isinstance(out, Decimal):
        return int(round(out))
    return out
