from typing import List
from datetime import datetime

def should_schedule_seconds(interval_seconds: int) -> List[int]:
    now = datetime.utcnow().timestamp()
    remaining = interval_seconds - (now % interval_seconds)
    result = []
    while remaining < 60:
        result.append(remaining)
        remaining += interval_seconds
    return result