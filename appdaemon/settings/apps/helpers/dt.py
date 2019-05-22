"""Define date/time utilities."""
from datetime import datetime, time, timedelta

DEFAULT_BLACKOUT_START = time(22, 0)
DEFAULT_BLACKOUT_END = time(8, 0)


def ceil_dt(target_dt: datetime, delta: timedelta) -> datetime:
    """Round a datetime up to the nearest delta."""
    return target_dt + (datetime.min - target_dt) % delta


def get_next_blackout_end(target: datetime) -> datetime:
    """Get the next instance of a target datetime outside of the blackout."""
    target_date = target.date()
    active_time = target.time()

    if active_time > DEFAULT_BLACKOUT_END:
        target_date = target_date + timedelta(days=1)

    return datetime.combine(target_date, DEFAULT_BLACKOUT_END)


def in_blackout(target: time = None) -> bool:
    """Return whether we're in the blackout."""
    kwargs = {}
    if target:
        kwargs['target'] = target
    return time_is_between(
        DEFAULT_BLACKOUT_START, DEFAULT_BLACKOUT_END, **kwargs)


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
