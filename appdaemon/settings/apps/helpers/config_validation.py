"""Define voluptuous helpers."""
from typing import Any, Sequence, TypeVar, Union

import voluptuous as vol

T = TypeVar('T')  # pylint: disable=invalid-name


def ensure_list(value: Union[T, Sequence[T]]) -> Sequence[T]:
    """Wrap value in list if it is not one."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def entity_id(value: Any) -> str:
    """Validate whether a passed value is an entity ID."""
    value = str(value).lower()
    if '.' in value:
        return value

    raise vol.Invalid('Invalid entity ID: {0}'.format(value))
