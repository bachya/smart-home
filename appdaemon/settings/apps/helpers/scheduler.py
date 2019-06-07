"""Define scheduling utilities."""
import datetime
from typing import Callable, List


def run_on_days(
    hass, callback: Callable[..., None], day_list: list, start: datetime.time, **kwargs
) -> List[str]:
    """Run a callback on certain days (at the specified time)."""
    handle = []
    upcoming_days = []

    today = hass.date()
    todays_event = datetime.datetime.combine(today, start)

    if todays_event > hass.datetime():
        if today.strftime("%A") in day_list:
            upcoming_days.append(today)

    for day_number in range(1, 8):
        day = today + datetime.timedelta(days=day_number)
        if day.strftime("%A") in day_list:
            if len(upcoming_days) < len(day_list):
                upcoming_days.append(day)

    for day in upcoming_days:
        event = datetime.datetime.combine(day, start)
        handle.append(hass.run_every(callback, event, 604800, **kwargs))

    return handle


def run_on_weekdays(
    hass, callback: Callable[..., None], start: datetime.time, **kwargs
) -> list:
    """Run a callback on weekdays (at the specified time)."""
    return hass.run_on_days(
        callback,
        ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
        start,
        **kwargs
    )


def run_on_weekend_days(
    hass, callback: Callable[..., None], start: datetime.time, **kwargs
) -> list:
    """Run a callback on weekend days (at the specified time)."""
    return hass.run_on_days(callback, ["Friday", "Saturday"], start, **kwargs)
