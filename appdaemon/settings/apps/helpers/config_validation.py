"""Define voluptuous helpers."""
from datetime import time as time_sys
from typing import Any, Callable, Dict, Sequence, TypeVar, Union

import voluptuous as vol

from util.dt import parse_time

T = TypeVar("T")  # pylint: disable=invalid-name


def ensure_list(value: Union[T, Sequence[T]]) -> Sequence[T]:
    """Wrap value in list if it is not one."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def entity_id(value: Any) -> str:
    """Validate whether a passed value is an entity ID."""
    value = str(value).lower()
    if "." in value:
        return value

    raise vol.Invalid("Invalid entity ID: {0}".format(value))


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


def time(value) -> time_sys:
    """Validate and transform a time."""
    if isinstance(value, time_sys):
        return value

    try:
        time_val = parse_time(value)
    except TypeError:
        raise vol.Invalid("Not a parseable type")

    if time_val is None:
        raise vol.Invalid("Invalid time specified: {}".format(value))

    return time_val
