"""Define people."""
from enum import Enum
from typing import Union

from core import Base
from const import CONF_PEOPLE
from helper import most_common

HANDLE_5_MINUTE_TIMER = '5_minute'
HANDLE_24_HOUR_TIMER = '24_hour'


class Person(Base):
    """Define a class to represent a person."""

    def configure(self) -> None:
        """Configure."""

        # Get the raw state of the device trackers and seed the home state:
        self._raw_state = self._most_common_raw_state()
        if self._raw_state == 'home':
            self._home_state = self.presence_manager.HomeStates.home
        else:
            self._home_state = self.presence_manager.HomeStates.away

        # Store a global reference to this person:
        self.global_vars.setdefault(CONF_PEOPLE, [])
        self.global_vars[CONF_PEOPLE].append(self)

        # Listen for changes to any of the person's device trackers:
        for device_tracker in self.entity_ids['device_trackers']:
            kind = self.get_state(device_tracker, attribute='source_type')
            if kind == 'router':
                self.listen_state(
                    self._device_tracker_changed_cb,
                    device_tracker,
                    old='not_home')
            else:
                self.listen_state(
                    self._device_tracker_changed_cb, device_tracker)

        # Render the initial state of the presence sensor:
        self._render_presence_status_sensor()

    @property
    def first_name(self) -> str:
        """Return the person's name."""
        return self.name.title()

    @property
    def home_state(self) -> Enum:
        """Return the person's human-friendly home state."""
        return self._home_state

    @home_state.setter
    def home_state(self, state: Enum) -> None:
        """Set the home-friendly home state."""
        original_state = self._home_state
        self._home_state = state
        self._fire_presence_change_event(original_state, state)

    @property
    def notifiers(self) -> list:
        """Return the notifiers associated with the person."""
        return self.entity_ids['notifiers']

    @property
    def push_device_id(self) -> str:
        """Get the iOS device ID for push notifications."""
        return self.properties.get('push_device_id')

    def _check_transition_cb(self, kwargs: dict) -> None:
        """Transition the user's home state (if appropriate)."""
        current_state = kwargs['current_state']

        if not self._home_state == kwargs['current_state']:
            return

        if current_state == self.presence_manager.HomeStates.just_arrived:
            self.home_state = self.presence_manager.HomeStates.home
        elif current_state == self.presence_manager.HomeStates.just_left:
            self.home_state = self.presence_manager.HomeStates.away
        elif current_state == self.presence_manager.HomeStates.away:
            self.home_state = self.presence_manager.HomeStates.extended_away

        # Re-render the sensor:
        self._render_presence_status_sensor()

    def _device_tracker_changed_cb(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Respond when a device tracker changes."""
        if self._raw_state == new:
            return

        self._raw_state = new

        # Cancel any old timers:
        for handle in (HANDLE_5_MINUTE_TIMER, HANDLE_24_HOUR_TIMER):
            if handle in self.handles:
                handle = self.handles.pop(handle)
                self.cancel_timer(handle)

        # Set the home state and schedule transition checks (Just Left -> Away,
        # for example) for various points in the future:
        if new == 'home':
            self.home_state = self.presence_manager.HomeStates.just_arrived
            self.handles[HANDLE_5_MINUTE_TIMER] = self.run_in(
                self._check_transition_cb,
                60 * 5,
                current_state=self.presence_manager.HomeStates.just_arrived)
        elif old == 'home':
            self.home_state = self.presence_manager.HomeStates.just_left
            self.handles[HANDLE_5_MINUTE_TIMER] = self.run_in(
                self._check_transition_cb,
                60 * 5,
                current_state=self.presence_manager.HomeStates.just_left)
            self.handles[HANDLE_24_HOUR_TIMER] = self.run_in(
                self._check_transition_cb,
                60 * 60 * 24,
                current_state=self.presence_manager.HomeStates.away)

        # Re-render the sensor:
        self._render_presence_status_sensor()

    def _fire_presence_change_event(self, old: Enum, new: Enum) -> None:
        """Fire a presence change event."""
        if new in (self.presence_manager.HomeStates.just_arrived,
                   self.presence_manager.HomeStates.home):
            states = [
                self.presence_manager.HomeStates.just_arrived,
                self.presence_manager.HomeStates.home
            ]
        else:
            states = [new]

        first = self.presence_manager.only_one(*states)

        self.fire_event(
            'PRESENCE_CHANGE',
            person=self.first_name,
            old=old.value,
            new=new.value,
            first=first)

    def _most_common_raw_state(self) -> str:
        """Get the most common raw state from the person's device trackers."""
        return most_common([
            self.get_tracker_state(dt)
            for dt in self.entity_ids['device_trackers']
        ])

    def _render_presence_status_sensor(self) -> None:
        """Update the sensor in the UI."""
        if self._home_state in (self.presence_manager.HomeStates.home,
                                self.presence_manager.HomeStates.just_arrived):
            picture_state = 'home'
        else:
            picture_state = 'away'

        if self._home_state:
            state = self._home_state.value
        else:
            state = self._raw_state

        self.set_state(
            self.entity_ids['presence_status_sensor'],
            state=state,
            attributes={
                'friendly_name':
                    self.first_name,
                'entity_picture':
                    '/local/{0}-{1}.png'.format(self.name, picture_state),
            })
