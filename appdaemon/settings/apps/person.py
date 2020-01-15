"""Define people."""
from typing import TYPE_CHECKING, Union

import voluptuous as vol

from const import (
    CONF_ENTITY_IDS,
    CONF_NOTIFIERS,
    CONF_PEOPLE,
    CONF_PROPERTIES,
    EVENT_PRESENCE_CHANGE,
)
from core import APP_SCHEMA, Base
from helpers import config_validation as cv

if TYPE_CHECKING:
    from presence import PresenceManager

CONF_GEOCODED_LOCATION = "geocoded_location"
CONF_PERSON = "person"
CONF_PRESENCE_STATUS_SENSOR = "presence_status_sensor"
CONF_PUSH_DEVICE_ID = "push_device_id"

HANDLE_5_MINUTE_TIMER = "5_minute"
HANDLE_24_HOUR_TIMER = "24_hour"

TRANSITION_DURATION_AWAY = 60 * 60 * 24
TRANSITION_DURATION_JUST_ARRIVED = 60 * 5
TRANSITION_DURATION_JUST_LEFT = 60 * 5


class Person(Base):
    """Define a class to represent a person."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_IDS): vol.Schema(
                {
                    vol.Required(CONF_PERSON): cv.entity_id,
                    vol.Required(CONF_NOTIFIERS): cv.ensure_list,
                    vol.Required(CONF_PRESENCE_STATUS_SENSOR): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            ),
            vol.Optional(CONF_PROPERTIES, default={}): vol.Schema(
                {vol.Optional(CONF_PUSH_DEVICE_ID): str}, extra=vol.ALLOW_EXTRA
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        # "Seed" the person's non-binary state:
        self._last_raw_state = self.state
        if self.state == "home":
            self._non_binary_state = self.presence_manager.HomeStates.home
        else:
            self._non_binary_state = self.presence_manager.HomeStates.away

        # Store a global reference to this person:
        if CONF_PEOPLE not in self.global_vars:
            self.global_vars[CONF_PEOPLE] = []
        self.global_vars[CONF_PEOPLE].append(self)

        # Listen to state changes for the `person` entity:
        self.listen_state(self._on_person_state_change, self.entity_ids[CONF_PERSON])

        # # Render the initial state of the presence sensor:
        self._render_presence_status_sensor()

    @property
    def first_name(self) -> str:
        """Return the person's name."""
        return self.name.title()

    @property
    def geocoded_location(self) -> str:
        """Return the person's reverse-geocoded address."""
        return self.get_state(self.entity_ids[CONF_GEOCODED_LOCATION])

    @property
    def non_binary_state(self) -> "PresenceManager.HomeStates":
        """Return the person's human-friendly non-binary state."""
        return self._non_binary_state

    @non_binary_state.setter
    def non_binary_state(self, state: "PresenceManager.HomeStates") -> None:
        """Set the home-friendly home state."""
        original_state = self._non_binary_state
        self._non_binary_state = state
        self._fire_presence_change_event(original_state, state)

    @property
    def notifiers(self) -> list:
        """Return the notifiers associated with the person."""
        return self.entity_ids[CONF_NOTIFIERS]

    @property
    def state(self) -> str:
        """Get the person's raw entity state."""
        return self.get_state(self.entity_ids[CONF_PERSON])

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

    def _on_person_state_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Respond when the person entity changes state."""
        # `person` entities can update their state to the same value as before; if this
        # occurs, return immediately:
        if self._last_raw_state == new:
            return
        self._last_raw_state = new

        # Cancel any old timers:
        for handle_key in (HANDLE_5_MINUTE_TIMER, HANDLE_24_HOUR_TIMER):
            if handle_key not in self.handles:
                continue
            handle = self.handles.pop(handle_key)
            self.cancel_timer(handle)

        # Set the home state and schedule transition checks (Just Left -> Away,
        # for example) for various points in the future:
        if new == "home":
            self.non_binary_state = self.presence_manager.HomeStates.just_arrived
            self.handles[HANDLE_5_MINUTE_TIMER] = self.run_in(
                self._on_transition_state,
                TRANSITION_DURATION_JUST_ARRIVED,
                current_state=self.presence_manager.HomeStates.just_arrived,
            )
        elif old == "home":
            self.non_binary_state = self.presence_manager.HomeStates.just_left
            self.handles[HANDLE_5_MINUTE_TIMER] = self.run_in(
                self._on_transition_state,
                TRANSITION_DURATION_JUST_LEFT,
                current_state=self.presence_manager.HomeStates.just_left,
            )
            self.handles[HANDLE_24_HOUR_TIMER] = self.run_in(
                self._on_transition_state,
                TRANSITION_DURATION_AWAY,
                current_state=self.presence_manager.HomeStates.away,
            )

        # Re-render the sensor:
        self._render_presence_status_sensor()

    def _on_transition_state(self, kwargs: dict) -> None:
        """Transition the user's home state (if appropriate)."""
        current_state = kwargs["current_state"]

        if current_state == self.presence_manager.HomeStates.just_arrived:
            self.non_binary_state = self.presence_manager.HomeStates.home
        elif current_state == self.presence_manager.HomeStates.just_left:
            self.non_binary_state = self.presence_manager.HomeStates.away
        elif current_state == self.presence_manager.HomeStates.away:
            self.non_binary_state = self.presence_manager.HomeStates.extended_away

        # Re-render the sensor:
        self._render_presence_status_sensor()

    def _render_presence_status_sensor(self) -> None:
        """Update the sensor in the UI."""
        if self._last_raw_state == "home":
            picture_state = "home"
        else:
            picture_state = "away"

        if self.state in ("home", "not_home"):
            state = self._non_binary_state.value
        else:
            state = self.state

        self.set_state(
            self.entity_ids[CONF_PRESENCE_STATUS_SENSOR],
            state=state,
            attributes={
                "friendly_name": self.first_name,
                "entity_picture": f"/local/{self.name}-{picture_state}.png",
                "geocoded_location": self.geocoded_location,
            },
        )
