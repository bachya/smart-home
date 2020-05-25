"""Define automations for switches."""
from core import Base

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
