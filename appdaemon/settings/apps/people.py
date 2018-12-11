"""Define people."""
# pylint: disable=attribute-defined-outside-init,unused-argument

from enum import Enum
from typing import Union

from automation import Base  # type: ignore
from const import CONF_PEOPLE
from util import most_common


class Person(Base):
    """Define a class to represent a person."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        # Store a global reference to this person:
        self.global_vars.setdefault(CONF_PEOPLE, [])
        self.global_vars[CONF_PEOPLE].append(self)

        # (Extended) Away -> Just Arrived
        self.listen_state(
            self._change_input_select_cb,
            self.properties['at_home_sensor'],
            old='off',
            new='on',
            target_state=self.presence_manager.HomeStates.just_arrived)

        # Just Arrived -> Home
        self.listen_state(
            self._change_input_select_cb,
            self.presence_input_select,
            new=self.presence_manager.HomeStates.just_arrived.value,
            duration=60 * 5,
            target_state=self.presence_manager.HomeStates.home)

        # Home -> Just Left
        self.listen_state(
            self._change_input_select_cb,
            self.properties['at_home_sensor'],
            old='on',
            new='off',
            target_state=self.presence_manager.HomeStates.just_left)

        # Just Left -> Away
        self.listen_state(
            self._change_input_select_cb,
            self.presence_input_select,
            new=self.presence_manager.HomeStates.just_left.value,
            duration=60 * 5,
            target_state=self.presence_manager.HomeStates.away)

        # Away -> Extended Away
        self.listen_state(
            self._change_input_select_cb,
            self.presence_input_select,
            new=self.presence_manager.HomeStates.away.value,
            duration=60 * 60 * 24,
            target_state=self.presence_manager.HomeStates.extended_away)

        # Listen for all changes to the presence input select:
        self.listen_state(
            self._input_select_changed_cb, self.presence_input_select)

        # Listen for changes to the device trackers (to initiate re-rendering
        # if needed):
        for tracker in self.device_trackers:
            self.listen_state(self._device_tracker_changed_cb, tracker)

        # Render the presence sensor immediately upon init:
        self._render_presence_status_sensor()

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
        raw_location = most_common([
            self.get_tracker_state(tracker_entity)
            for tracker_entity in self.properties['device_trackers']
        ])

        if raw_location not in ('home', 'not_home'):
            return raw_location

        return self.get_state(self.presence_input_select)

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
    def presence_sensor(self) -> str:
        """Return the entity ID of the generated presence status sensor."""
        return 'sensor.{0}_presence_status'.format(self.name)

    @property
    def push_device_id(self) -> str:
        """Get the iOS device ID for push notifications."""
        return self.properties.get('push_device_id')

    def _change_input_select_cb(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Change state of a home presence input select."""
        target_state = kwargs['target_state']
        self.presence_input_select = target_state

    def _device_tracker_changed_cb(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Respond when a device tracker changes state."""
        self._render_presence_status_sensor()

    def _input_select_changed_cb(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Respond when the home presence input select changes."""
        if old == new:
            return

        new_state = self.presence_manager.HomeStates(new)
        if new_state in (self.presence_manager.HomeStates.just_arrived,
                         self.presence_manager.HomeStates.home):
            states = [
                self.presence_manager.HomeStates.just_arrived,
                self.presence_manager.HomeStates.home
            ]
        else:
            states = [new_state]

        first = self.presence_manager.only_one(*states)

        self.fire_event(
            'PRESENCE_CHANGE',
            person=self.first_name,
            old=old,
            new=new,
            first=first)

        self._render_presence_status_sensor()

    def _render_presence_status_sensor(self):
        """Update the presence status sensor."""
        if self.location in ('Home', 'Just Arrived'):
            picture_state = 'home'
        else:
            picture_state = 'away'

        self.set_state(
            self.presence_sensor,
            state=self.location,
            attributes={
                'friendly_name': self.first_name,
                'entity_picture':
                    '/local/{0}-{1}.png'.format(self.name, picture_state),
            })
