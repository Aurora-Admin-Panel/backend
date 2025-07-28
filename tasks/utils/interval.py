from typing import List, Optional
from datetime import datetime, UTC

def should_schedule_seconds(interval_seconds: int) -> List[int]:
    now = datetime.now(UTC).timestamp()
    remaining = interval_seconds - (now % interval_seconds)
    result = []
    while remaining < 60:
        result.append(remaining)
        remaining += interval_seconds
    return result

def compute_exponential_backoff(
    last_connect: Optional[int],
    base_interval: int = 60,     # Starting retry interval in seconds
    factor: int = 2,            # Exponential growth factor
    max_interval: int = 3600,   # Maximum interval to avoid unbounded delay (1 hour here)
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

    now = datetime.now(UTC)  # or datetime.now(UTC) if you’re consistently using pytz/zoneinfo
    elapsed = (now - last_connect).total_seconds()

    # Simple approach:
    # Keep doubling the base_interval until it exceeds the time since last_connect.
    # Once it does, we stop—that's our new delay.
    delay = base_interval
    while delay < elapsed:
        delay *= factor
        if delay > max_interval:
            delay = max_interval
            break

    return int(delay)