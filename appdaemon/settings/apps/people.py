"""Define people."""
from typing import TYPE_CHECKING, Union

import voluptuous as vol

from const import (
    CONF_DEVICE_TRACKERS,
    CONF_ENTITY_IDS,
    CONF_NOTIFIERS,
    CONF_PEOPLE,
    CONF_PROPERTIES,
    EVENT_PRESENCE_CHANGE,
)
from core import APP_SCHEMA, Base
from helpers import config_validation as cv, most_common

if TYPE_CHECKING:
    from presence import PresenceManager

CONF_PRESENCE_STATUS_SENSOR = "presence_status_sensor"
CONF_PUSH_DEVICE_ID = "push_device_id"

HANDLE_5_MINUTE_TIMER = "5_minute"
HANDLE_24_HOUR_TIMER = "24_hour"


class Person(Base):
    """Define a class to represent a person."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {
                    vol.Required(CONF_DEVICE_TRACKERS): cv.ensure_list,
                    vol.Required(CONF_NOTIFIERS): cv.ensure_list,
                    vol.Required(CONF_PRESENCE_STATUS_SENSOR): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            ),
            CONF_PROPERTIES: vol.Schema(
                {vol.Optional(CONF_PUSH_DEVICE_ID): str}, extra=vol.ALLOW_EXTRA
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        # Get the raw state of the device trackers and seed the home state:
        self._raw_state = self._most_common_raw_state()
        if self._raw_state == "home":
            self._home_state = self.presence_manager.HomeStates.home
        else:
            self._home_state = self.presence_manager.HomeStates.away

        # Store a global reference to this person:
        if CONF_PEOPLE not in self.global_vars:
            self.global_vars[CONF_PEOPLE] = []
        self.global_vars[CONF_PEOPLE].append(self)

        # Listen for changes to any of the person's device trackers:
        for device_tracker in self.entity_ids[CONF_DEVICE_TRACKERS]:
            kind = self.get_state(device_tracker, attribute="source_type")
            if kind == "router":
                self.listen_state(
                    self._on_device_tracker_change, device_tracker, old="not_home"
                )
            else:
                self.listen_state(self._on_device_tracker_change, device_tracker)

        # Render the initial state of the presence sensor:
        self._render_presence_status_sensor()

    @property
    def first_name(self) -> str:
        """Return the person's name."""
        return self.name.title()

    @property
    def home_state(self) -> "PresenceManager.HomeStates":
        """Return the person's human-friendly home state."""
        return self._home_state

    @home_state.setter
    def home_state(self, state: "PresenceManager.HomeStates") -> None:
        """Set the home-friendly home state."""
        original_state = self._home_state
        self._home_state = state
        self._fire_presence_change_event(original_state, state)

    @property
    def notifiers(self) -> list:
        """Return the notifiers associated with the person."""
        return self.entity_ids[CONF_NOTIFIERS]

    @property
    def push_device_id(self) -> str:
        """Get the iOS device ID for push notifications."""
        return self.properties.get(CONF_PUSH_DEVICE_ID)

    def _fire_presence_change_event(
        self, old: "PresenceManager.HomeStates", new: "PresenceManager.HomeStates"
    ) -> None:
        """Fire a presence change event."""
        if new in (
            self.presence_manager.HomeStates.just_arrived,
            self.presence_manager.HomeStates.home,
        ):
            states = [
                self.presence_manager.HomeStates.just_arrived,
                self.presence_manager.HomeStates.home,
            ]
        else:
            states = [new]

        first = self.presence_manager.only_one(*states)

        self.fire_event(
            EVENT_PRESENCE_CHANGE,
            person=self.first_name,
            old=old.value,
            new=new.value,
            first=first,
        )

    def _most_common_raw_state(self) -> str:
        """Get the most common raw state from the person's device trackers."""
        return most_common(
            [self.get_tracker_state(dt) for dt in self.entity_ids[CONF_DEVICE_TRACKERS]]
        )

    def _on_device_tracker_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Respond when a device tracker changes."""
        if self._raw_state == new:
            return

        self._raw_state = new

        # Cancel any old timers:
        for handle_key in (HANDLE_5_MINUTE_TIMER, HANDLE_24_HOUR_TIMER):
            if handle_key in self.handles:
                handle = self.handles.pop(handle_key)
                self.cancel_timer(handle)

        # Set the home state and schedule transition checks (Just Left -> Away,
        # for example) for various points in the future:
        if new == "home":
            self.home_state = self.presence_manager.HomeStates.just_arrived
            self.handles[HANDLE_5_MINUTE_TIMER] = self.run_in(
                self._on_transition_state,
                60 * 5,
                current_state=self.presence_manager.HomeStates.just_arrived,
            )
        elif old == "home":
            self.home_state = self.presence_manager.HomeStates.just_left
            self.handles[HANDLE_5_MINUTE_TIMER] = self.run_in(
                self._on_transition_state,
                60 * 5,
                current_state=self.presence_manager.HomeStates.just_left,
            )
            self.handles[HANDLE_24_HOUR_TIMER] = self.run_in(
                self._on_transition_state,
                60 * 60 * 24,
                current_state=self.presence_manager.HomeStates.away,
            )

        # Re-render the sensor:
        self._render_presence_status_sensor()

    def _on_transition_state(self, kwargs: dict) -> None:
        """Transition the user's home state (if appropriate)."""
        current_state = kwargs["current_state"]

        if not self._home_state == kwargs["current_state"]:
            return

        if current_state == self.presence_manager.HomeStates.just_arrived:
            self.home_state = self.presence_manager.HomeStates.home
        elif current_state == self.presence_manager.HomeStates.just_left:
            self.home_state = self.presence_manager.HomeStates.away
        elif current_state == self.presence_manager.HomeStates.away:
            self.home_state = self.presence_manager.HomeStates.extended_away

        # Re-render the sensor:
        self._render_presence_status_sensor()

    def _render_presence_status_sensor(self) -> None:
        """Update the sensor in the UI."""
        if self._home_state in (
            self.presence_manager.HomeStates.home,
            self.presence_manager.HomeStates.just_arrived,
        ):
            picture_state = "home"
        else:
            picture_state = "away"

        if self._home_state:
            state = self._home_state.value
        else:
            state = self._raw_state

        self.set_state(
            self.entity_ids[CONF_PRESENCE_STATUS_SENSOR],
            state=state,
            attributes={
                "friendly_name": self.first_name,
                "entity_picture": "/local/{0}-{1}.png".format(self.name, picture_state),
            },
        )
