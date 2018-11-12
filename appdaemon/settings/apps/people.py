"""Define people."""
# pylint: disable=attribute-defined-outside-init

from enum import Enum

from automation import Base  # type: ignore
from util import most_common

PEOPLE_KEY = 'people'


class Person(Base):
    """Define a class to represent a person."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.global_vars.setdefault(PEOPLE_KEY, [])
        self.global_vars[PEOPLE_KEY].append(self)

    @property
    def at_home_sensor(self) -> str:
        """Return the bayesian sensor defining the person's home status."""
        return self.properties['at_home_sensor']

    @property
    def device_trackers(self) -> list:
        """Return the device trackers associated with the person."""
        return self.properties['device_trackers']

    @property
    def first_name(self) -> str:
        """Return the person's name."""
        return self.name.title()

    @property
    def location(self) -> str:
        """Get the current location from combined device trackers."""
        return most_common([
            self.get_tracker_state(tracker_entity)
            for tracker_entity in self.properties['device_trackers']
        ])

    @property
    def notifiers(self) -> list:
        """Return the notifiers associated with the person."""
        return self.properties['notifiers']

    @property
    def presence_input_select(self) -> str:
        """Return the input select related to the person's presence."""
        return self.properties['presence_input_select']

    @presence_input_select.setter
    def presence_input_select(self, value: Enum) -> None:
        self.select_option(
            self.properties['presence_input_select'], value.value)

    @property
    def push_device_id(self) -> str:
        """Get the iOS device ID for push notifications."""
        return self.properties.get('push_device_id')
