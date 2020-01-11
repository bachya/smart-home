"""Define automations for switches."""
from datetime import timedelta
from typing import Union

import voluptuous as vol
from const import (
    CONF_DURATION,
    CONF_END_TIME,
    CONF_ENTITY_IDS,
    CONF_PROPERTIES,
    CONF_START_TIME,
    CONF_STATE,
)
from core import APP_SCHEMA, Base
from helpers import config_validation as cv

CONF_RETURN_DELAY = "return_delay"
CONF_SWITCH = "switch"
CONF_TIMER_SLIDER = "timer_slider"
CONF_WINDOW = "window"

HANDLE_TIMER = "timer"
HANDLE_TOGGLE_IN_WINDOW = "in_window"
HANDLE_TOGGLE_OUT_WINDOW = "out_window"
HANDLE_TOGGLE_STATE = "toggle_state"
HANDLE_TOGGLE_STATE_RETURN = "toggle_state_return"
HANDLE_VACATION_MODE = "vacation_mode"

SOLAR_EVENTS = ("sunrise", "sunset")
TOGGLE_STATES = ("closed", "off", "on", "open")


class BaseSwitch(Base):
    """Define a base feature for all switches."""

    @property
    def state(self) -> bool:
        """Return the current state of the switch."""
        return self.get_state(self.entity_ids["switch"])

    def _on_schedule_toggle(self, kwargs: dict) -> None:
        """Turn off the switch at a certain time."""
        if kwargs.get("opposite"):
            self.toggle(opposite_of=kwargs["state"])
        else:
            self.toggle(state=kwargs["state"])

    def toggle(self, *, state: str = None, opposite_of: str = None) -> None:
        """Toggle the switch state."""
        if not state and not opposite_of:
            self.error("No state value provided")
            return

        if state:
            _state = state
        elif opposite_of == "off":
            _state = "on"
        else:
            _state = "off"

        if self.state == "off" and _state == "on":
            self.log("Turning on: %s", self.entity_ids["switch"])
            self.turn_on(self.entity_ids["switch"])
        elif self.state == "on" and _state == "off":
            self.log("Turning off: %s", self.entity_ids["switch"])
            self.turn_off(self.entity_ids["switch"])


class BaseZwaveSwitch(BaseSwitch):
    """Define a Zwave switch."""

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self.on_double_tap_up,
            "zwave.node_event",
            entity_id=self.entity_ids["zwave_device"],
            basic_level=255,
        )

        self.listen_event(
            self.on_double_tap_down,
            "zwave.node_event",
            entity_id=self.entity_ids["zwave_device"],
            basic_level=0,
        )

    def on_double_tap_down(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Stub out method signature."""
        pass

    def on_double_tap_up(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Stub out method signature."""
        pass


class PresenceFailsafe(BaseSwitch):
    """Define a feature to restrict activation when we're not home."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_SWITCH): cv.entity_id}, extra=vol.ALLOW_EXTRA
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_switch_activate,
            self.entity_ids[CONF_SWITCH],
            new="on",
            constrain_noone="just_arrived,home",
        )

    def _on_switch_activate(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Turn the switch off if no one is home."""
        self.log("No one home; not allowing switch to activate")
        self.toggle(state="off")


class SleepTimer(BaseSwitch):
    """Define a feature to turn a switch off after an amount of time."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {
                    vol.Required(CONF_SWITCH): cv.entity_id,
                    vol.Required(CONF_TIMER_SLIDER): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_switch_turned_off, self.entity_ids[CONF_SWITCH], new="off",
        )
        self.listen_state(
            self._on_timer_change, self.entity_ids[CONF_TIMER_SLIDER],
        )

    def _on_timer_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Start/stop a sleep timer for this switch."""
        minutes = int(float(new))

        if minutes == 0:
            self.log("Deactivating sleep timer")
            self.toggle(state="off")

            if HANDLE_TIMER in self.handles:
                cancel = self.handles.pop(HANDLE_TIMER)
                self.cancel_timer(cancel)
        else:
            self.log("Activating sleep timer: %s minutes", minutes)
            self.toggle(state="on")
            self.handles[HANDLE_TIMER] = self.run_in(
                self._on_timer_complete, minutes * 60
            )

    def _on_switch_turned_off(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Reset the sleep timer when the switch turns off."""
        self.set_value(self.entity_ids[CONF_TIMER_SLIDER], 0)

    def _on_timer_complete(self, kwargs: dict) -> None:
        """Turn off a switch at the end of sleep timer."""
        self.log("Sleep timer over; turning switch off")
        self.set_value(self.entity_ids[CONF_TIMER_SLIDER], 0)


class ToggleOnInterval(BaseSwitch):
    """Define a feature to toggle the switch at intervals."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_SWITCH): cv.entity_id}, extra=vol.ALLOW_EXTRA
            ),
            CONF_PROPERTIES: vol.Schema(
                {
                    vol.Required(CONF_STATE): vol.In(TOGGLE_STATES),
                    vol.Required(CONF_START_TIME): str,
                    vol.Required(CONF_END_TIME): str,
                    vol.Required(CONF_DURATION): int,
                    vol.Required(CONF_WINDOW): int,
                },
                extra=vol.ALLOW_EXTRA,
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.run_daily(
            self._on_start_cycle, self.parse_time(self.properties[CONF_START_TIME]),
        )

        self.run_daily(
            self._on_stop_cycle, self.parse_time(self.properties[CONF_END_TIME]),
        )

        if (
            self.now_is_between(
                self.properties[CONF_START_TIME], self.properties[CONF_END_TIME]
            )
            and self.enabled
        ):
            self._on_start_cycle({})

    def on_disable(self) -> None:
        """Kill any existing handles if the app is disabled."""
        self._on_stop_cycle({})

    def _on_start_cycle(self, kwargs: dict) -> None:
        """Start the toggle cycle."""
        self.handles[HANDLE_TOGGLE_IN_WINDOW] = self.run_every(
            self._on_schedule_toggle,
            self.datetime(),
            self.properties[CONF_WINDOW],
            state=self.properties[CONF_STATE],
        )
        self.handles[HANDLE_TOGGLE_OUT_WINDOW] = self.run_every(
            self._on_schedule_toggle,
            self.datetime() + timedelta(seconds=self.properties[CONF_DURATION]),
            self.properties[CONF_WINDOW],
            state=self.properties[CONF_STATE],
            opposite=True,
        )

    def _on_stop_cycle(self, kwargs: dict) -> None:
        """Stop the toggle cycle."""
        for handle in (HANDLE_TOGGLE_IN_WINDOW, HANDLE_TOGGLE_OUT_WINDOW):
            if handle not in self.handles:
                continue
            name = self.handles.pop(handle)
            self.cancel_timer(name)

        self.toggle(opposite_of=self.properties[CONF_STATE])
