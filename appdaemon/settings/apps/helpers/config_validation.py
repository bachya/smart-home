"""Define voluptuous helpers."""
# pylint: disable=invalid-name
from datetime import date as date_sys, time as time_sys, timedelta
from typing import Any, Callable, Dict, List, TypeVar, Union

import voluptuous as vol

import util.dt as dt_util

T = TypeVar("T")  # pylint: disable=invalid-name

TIME_PERIOD_ERROR = "offset {} should be format 'HH:MM' or 'HH:MM:SS'"


def ensure_list(value: Union[T, List[T], None]) -> List[T]:
    """Wrap value in list if it is not one."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def entity_id(value: Any) -> str:
    """Validate whether a passed value is an entity ID."""
    value = str(value).lower()
    if "." in value:
        return value

    raise vol.Invalid("invalid entity ID: {0}".format(value))


# Adapted from:
# https://github.com/alecthomas/voluptuous/issues/115#issuecomment-144464666
def has_at_least_one_key(*keys: str) -> Callable:
    """Validate that at least one key exists."""

    def validate(obj: Dict) -> Dict:
        """Test keys exist in dict."""
        if not isinstance(obj, dict):
            raise vol.Invalid("expected dictionary")

        for k in obj.keys():
            if k in keys:
                return obj
        raise vol.Invalid("must contain one of {}.".format(", ".join(keys)))

    return validate


def icon(value: Any) -> str:
    """Validate that the value is a valid icon string."""
    str_value = str(value)

    if ":" in str_value:
        return str_value

    raise vol.invalid('icons should be specified in the form "prefix:name"')


def notification_target(value: Any) -> str:
    """Validate that the value is a valid notification manager target."""
    str_value = str(value)

    if ":" in str_value:
        return str_value

    raise vol.invalid(
        'notification targets should be specified in the form "type:name"'
    )


positive_int = vol.All(vol.Coerce(int), vol.Range(min=0))


def string(value: Any) -> str:
    """Coerce value to string, except for None."""
    if value is None:
        raise vol.Invalid("string value is None")
    if isinstance(value, (list, dict)):
        raise vol.Invalid("value should be a string")

    return str(value)


time_period_dict = vol.All(
    dict,
    vol.Schema(
        {
            "days": vol.Coerce(int),
            "hours": vol.Coerce(int),
            "minutes": vol.Coerce(int),
            "seconds": vol.Coerce(int),
            "milliseconds": vol.Coerce(int),
        }
    ),
    has_at_least_one_key("days", "hours", "minutes", "seconds", "milliseconds"),
    lambda value: timedelta(**value),
)


def time(value: Any) -> time_sys:
    """Validate and transform a time."""
    if isinstance(value, time_sys):
        return value

    try:
        time_val = dt_util.parse_time(value)
    except TypeError:
        raise vol.Invalid("Not a parseable type")

    if time_val is None:
        raise vol.Invalid(f"Invalid time specified: {value}")

    return time_val


def date(value: Any) -> date_sys:
    """Validate and transform a date."""
    if isinstance(value, date_sys):
        return value

    try:
        date_val = dt_util.parse_date(value)
    except TypeError:
        raise vol.Invalid("Not a parseable type")

    if date_val is None:
        raise vol.Invalid("Could not parse date")

    return date_val


def time_period_str(value: str) -> timedelta:
    """Validate and transform time offset."""
    if isinstance(value, int):
        raise vol.Invalid("Make sure you wrap time values in quotes")
    if not isinstance(value, str):
        raise vol.Invalid(TIME_PERIOD_ERROR.format(value))

    negative_offset = False
    if value.startswith("-"):
        negative_offset = True
        value = value[1:]
    elif value.startswith("+"):
        value = value[1:]

    try:
        parsed = [int(x) for x in value.split(":")]
    except ValueError:
        raise vol.Invalid(TIME_PERIOD_ERROR.format(value))

    if len(parsed) == 2:
        hour, minute = parsed
        second = 0
    elif len(parsed) == 3:
        hour, minute, second = parsed
    else:
        raise vol.Invalid(TIME_PERIOD_ERROR.format(value))

    offset = timedelta(hours=hour, minutes=minute, seconds=second)

    if negative_offset:
        offset *= -1

    return offset


def time_period_seconds(value: Union[int, str]) -> timedelta:
    """Validate and transform seconds to a time offset."""
    try:
        return timedelta(seconds=int(value))
    except (ValueError, TypeError):
        raise vol.Invalid(f"Expected seconds, got {value}")


time_period = vol.Any(time_period_str, time_period_seconds, timedelta, time_period_dict)
