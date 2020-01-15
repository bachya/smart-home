"""Define automations for trash."""
import datetime
from math import ceil
from typing import Tuple

from core import Base
from helpers import grammatical_list_join, suffix_strftime
from helpers.scheduler import run_on_days
from notification import send_notification

CONF_NEXT_PICKUP_SENSOR = "next_pickup_sensor"
CONF_TRASH_TYPE_SENSORS = "trash_type_sensors"


class NotifyOfPickup(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify us of low batteries."""

    def configure(self) -> None:
        """Configure."""
        run_on_days(self, self._on_notify, ["Sunday"], datetime.time(20, 0, 0))

    def _on_notify(self, kwargs: dict) -> None:
        """Schedule the next pickup notification."""
        date, friendly_str = self.trash_manager.in_next_pickup_str()
        send_notification(
            self,
            "presence:home",
            friendly_str,
            title="Trash Reminder 🗑",
            when=datetime.datetime.combine(
                date - datetime.timedelta(days=1), datetime.time(20, 0, 0)
            ),
        )


class TrashManager(Base):
    """Define a class to represent a trash manager."""

    def in_next_pickup(self) -> Tuple[datetime.datetime, list]:
        """Return a list of pickup types in the next pickup."""
        pickup_datetime = datetime.datetime.strptime(
            self.get_state(self.args[CONF_NEXT_PICKUP_SENSOR]), "%Y-%m-%d"
        )
        pickup_types = [
            pickup_type
            for pickup_type, sensor in self.args[CONF_TRASH_TYPE_SENSORS].items()
            if self.get_state(sensor) == "on"
        ]

        return (pickup_datetime, pickup_types)

    def in_next_pickup_str(self) -> Tuple[datetime.datetime, str]:
        """Return a human-friendly string of next pickup info."""
        date, pickup_types = self.in_next_pickup()

        delta = ceil((date - self.datetime()).total_seconds() / 60 / 60 / 24)
        if delta == 1:
            relative_date_string = "tomorrow"
        else:
            relative_date_string = f"in {delta} days"

        grammatical_time = suffix_strftime("%A, %B {TH}", date)
        grammatical_types = grammatical_list_join(
            [pickup.replace("_", " ") for pickup in pickup_types]
        )
        response = (
            f"The next pickup is {relative_date_string} on {grammatical_time}. "
            f"It includes {grammatical_types}."
        )

        return (date, response)
