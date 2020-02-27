"""Define scheduling utilities."""
import datetime
from typing import Callable

from core import Base


def run_on_days(
    app: Base,
    callback: Callable[..., None],
    day_list: list,
    start: datetime.time,
    **kwargs
) -> Callable:
    """Run a callback on certain days (at the specified time)."""
    handles = []
    upcoming_days = []

    today = app.date()
    todays_event = datetime.datetime.combine(today, start)

    if todays_event > app.datetime():
        if today.strftime("%A") in day_list:
            upcoming_days.append(today)

    for day_number in range(1, 8):
        day = today + datetime.timedelta(days=day_number)
        if day.strftime("%A") in day_list:
            if len(upcoming_days) < len(day_list):
                upcoming_days.append(day)

    for day in upcoming_days:
        event = datetime.datetime.combine(day, start)
        handles.append(app.run_every(callback, event, 604800, **kwargs))

    def cancel():
        """Define a method to cancel all of the handles."""
        for handle in handles:
            app.cancel_timer(handle)

    return cancel


def run_on_weekdays(
    app: Base, callback: Callable[..., None], start: datetime.time, **kwargs
) -> list:
    """Run a callback on weekdays (at the specified time)."""
    return app.run_on_days(
        callback,
        ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
        start,
        **kwargs
    )


def run_on_weekend_days(
    app: Base, callback: Callable[..., None], start: datetime.time, **kwargs
) -> list:
    """Run a callback on weekend days (at the specified time)."""
    return app.run_on_days(callback, ["Friday", "Saturday"], start, **kwargs)
