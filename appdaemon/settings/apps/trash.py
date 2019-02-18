"""Define automations for trash."""
import datetime
from enum import Enum
from math import ceil
from typing import Tuple

from core import Base
from helper import grammatical_list_join, suffix_strftime
from helper.scheduler import run_on_days


class NotifyOfPickup(Base):
    """Define a feature to notify us of low batteries."""

    def configure(self) -> None:
        """Configure."""
        run_on_days(
            self,
            self.time_to_notify, ['Sunday'],
            datetime.time(20, 0, 0),
            constrain_input_boolean=self.enabled_entity_id,
            constrain_anyone='home')

    def time_to_notify(self, kwargs: dict) -> None:
        """Schedule the next pickup notification."""
        date, friendly_str = self.trash_manager.in_next_pickup_str()
        self.notification_manager.send(
            friendly_str,
            title='Trash Reminder 🗑',
            when=datetime.datetime.combine(
                date - datetime.timedelta(days=1), datetime.time(20, 0, 0)),
            target='home')


class TrashManager(Base):
    """Define a class to represent a trash manager."""

    class PickupTypes(Enum):
        """Define an enum for pickup types."""

        extra_trash = 'Extra Trash'
        recycling = 'Recycling'
        trash = 'Trash'

    def configure(self) -> None:
        """Configure."""
        self.sensors = {
            self.PickupTypes.extra_trash: 'sensor.extra_trash_pickup',
            self.PickupTypes.recycling: 'sensor.recycling_pickup',
            self.PickupTypes.trash: 'sensor.trash_pickup'
        }

    def in_next_pickup(self) -> Tuple[datetime.datetime, list]:
        """Return a list of pickup types in the next pickup."""
        return (
            datetime.datetime.strptime(
                self.get_state(
                    self.sensors[self.PickupTypes.trash],
                    attribute='pickup_date'), '%B %d, %Y'), [
                        t for t, entity in self.sensors.items()
                        if 'pickups' not in self.get_state(entity)
                    ])

    def in_next_pickup_str(self) -> Tuple[datetime.datetime, str]:
        """Return a human-friendly string of next pickup info."""
        date, pickup_types = self.in_next_pickup()

        delta = ceil((date - self.datetime()).total_seconds() / 60 / 60 / 24)
        if delta == 1:
            relative_date_string = 'tomorrow'
        else:
            relative_date_string = 'in {0} days'.format(delta)

        return (
            date, 'The next pickup is {0} on {1}. It will include {2}.'.format(
                relative_date_string, suffix_strftime('%A, %B {TH}', date),
                grammatical_list_join(
                    [p.value.lower().replace('_', ' ')
                     for p in pickup_types])))

    def when_next_pickup(self, pickup_type: Enum) -> str:
        """Return the relative date of next pickup for a particular type."""
        return self.get_state(self.sensors[pickup_type])  # type: ignore
