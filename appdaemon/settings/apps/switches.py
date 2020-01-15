"""Define automations for switches."""
from typing import Union

import voluptuous as vol
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
        return self.get_state(self.args["switch"])

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
            self.log("Turning on: %s", self.args["switch"])
            self.turn_on(self.args["switch"])
        elif self.state == "on" and _state == "off":
            self.log("Turning off: %s", self.args["switch"])
            self.turn_off(self.args["switch"])


class BaseZwaveSwitch(BaseSwitch):
    """Define a Zwave switch."""

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self.on_double_tap_up,
            "zwave.node_event",
            entity_id=self.args["zwave_device"],
            basic_level=255,
        )

        self.listen_event(
            self.on_double_tap_down,
            "zwave.node_event",
            entity_id=self.args["zwave_device"],
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

    APP_SCHEMA = APP_SCHEMA.extend({vol.Required(CONF_SWITCH): cv.entity_id})

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_switch_activate,
            self.args[CONF_SWITCH],
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
            vol.Required(CONF_SWITCH): cv.entity_id,
            vol.Required(CONF_TIMER_SLIDER): cv.entity_id,
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_state(self._on_switch_turned_off, self.args[CONF_SWITCH], new="off")
        self.listen_state(self._on_timer_change, self.args[CONF_TIMER_SLIDER])

    def _on_timer_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Start/stop a sleep timer for this switch."""
        minutes = int(float(new))

        if minutes == 0:
            self.log("Deactivating sleep timer")
            self.toggle(state="off")

            if HANDLE_TIMER in self.data:
                cancel = self.data.pop(HANDLE_TIMER)
                self.cancel_timer(cancel)
        else:
            self.log("Activating sleep timer: %s minutes", minutes)
            self.toggle(state="on")
            self.data[HANDLE_TIMER] = self.run_in(self._on_timer_complete, minutes * 60)

    def _on_switch_turned_off(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Reset the sleep timer when the switch turns off."""
        self.set_value(self.args[CONF_TIMER_SLIDER], 0)

    def _on_timer_complete(self, kwargs: dict) -> None:
        """Turn off a switch at the end of sleep timer."""
        self.log("Sleep timer over; turning switch off")
        self.set_value(self.args[CONF_TIMER_SLIDER], 0)
