"""Define date/time utilities."""
from datetime import datetime, time, timedelta


def ceil_dt(target_dt: datetime, delta: timedelta) -> datetime:
    """Round a datetime up to the nearest delta."""
    return target_dt + (datetime.min - target_dt) % delta


def relative_time_of_day(hass) -> str:
    """Return the relative time of day based on time."""
    greeting = None
    now = hass.datetime()

    if now.hour < 12:
        greeting = 'morning'
    elif 12 <= now.hour < 18:
        greeting = 'afternoon'
    else:
        greeting = 'evening'

    return greeting


def time_is_between(start: time, end: time, target: time = None) -> bool:
    """Check whether a target/now is between a start and end time."""
    if target:
        _target = target
    else:
        _target = datetime.now().time()

    if start < end:
        return end >= _target >= start
    return _target >= start or _target <= end
