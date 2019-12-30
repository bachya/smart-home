"""Define automations for switches."""
from datetime import timedelta
from random import randint
from typing import Callable, Union

import voluptuous as vol
from const import (
    CONF_DELAY,
    CONF_DURATION,
    CONF_END_TIME,
    CONF_ENTITY_IDS,
    CONF_EVENT,
    CONF_EVENT_DATA,
    CONF_PROPERTIES,
    CONF_START_TIME,
    CONF_STATE,
    TOGGLE_STATES,
)
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from helpers.scheduler import run_on_days

CONF_RETURN_DELAY = "return_delay"
CONF_RUN_ON_DAYS = "run_on_days"
CONF_SCHEDULE_TIME = "schedule_time"
CONF_SWITCH = "switch"
CONF_TARGET = "target"
CONF_TARGET_STATE = "target_state"
CONF_TIMER_SLIDER = "timer_slider"
CONF_WINDOW = "window"
CONF_ZWAVE_DEVICE = "zwave_device"

HANDLE_TIMER = "timer"
HANDLE_TOGGLE_IN_WINDOW = "in_window"
HANDLE_TOGGLE_OUT_WINDOW = "out_window"
HANDLE_TOGGLE_STATE = "toggle_state"
HANDLE_TOGGLE_STATE_RETURN = "toggle_state_return"
HANDLE_VACATION_MODE = "vacation_mode"

SOLAR_EVENTS = ("sunrise", "sunset")


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
            constrain_enabled=True,
        )

        self.listen_event(
            self.on_double_tap_down,
            "zwave.node_event",
            entity_id=self.entity_ids["zwave_device"],
            basic_level=0,
            constrain_enabled=True,
        )

    def on_double_tap_down(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Stub out method signature."""
        pass

    def on_double_tap_up(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Stub out method signature."""
        pass


class DoubleTapTimerSwitch(BaseZwaveSwitch):
    """Define a feature to double tap a switch on for a time."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {
                    vol.Required(CONF_TIMER_SLIDER): cv.entity_id,
                    vol.Required(CONF_ZWAVE_DEVICE): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            ),
            CONF_PROPERTIES: vol.Schema(
                {vol.Required(CONF_DURATION): int}, extra=vol.ALLOW_EXTRA
            ),
        }
    )

    def on_double_tap_up(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Turn on the target timer slider with a double up tap."""
        self.set_value(
            self.entity_ids[CONF_TIMER_SLIDER],
            round(self.properties[CONF_DURATION] / 60),
        )


class DoubleTapToggleSwitch(BaseZwaveSwitch):
    """Define a feature to toggle a switch with a double tab of this switch."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {
                    vol.Required(CONF_TARGET): cv.entity_id,
                    vol.Required(CONF_ZWAVE_DEVICE): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            ),
            CONF_PROPERTIES: vol.Schema(
                {vol.Required(CONF_DURATION): int}, extra=vol.ALLOW_EXTRA
            ),
        }
    )

    def on_double_tap_down(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Turn off the target switch with a double down tap."""
        self.turn_off(self.entity_ids[CONF_TARGET])

    def on_double_tap_up(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Turn on the target switch with a double up tap."""
        self.turn_on(self.entity_ids[CONF_TARGET])


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
            constrain_enabled=True,
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
            self._on_switch_turned_off,
            self.entity_ids[CONF_SWITCH],
            new="off",
            constrain_enabled=True,
        )
        self.listen_state(
            self._on_timer_change,
            self.entity_ids[CONF_TIMER_SLIDER],
            constrain_enabled=True,
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


class ToggleAtTime(BaseSwitch):
    """Define a feature to toggle a switch at a certain time."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_SWITCH): cv.entity_id}, extra=vol.ALLOW_EXTRA
            ),
            CONF_PROPERTIES: vol.Schema(
                {
                    vol.Required(CONF_SCHEDULE_TIME): str,
                    vol.Required(CONF_STATE): vol.In(TOGGLE_STATES),
                    vol.Optional(CONF_RUN_ON_DAYS): cv.ensure_list,
                },
                extra=vol.ALLOW_EXTRA,
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        kwargs = {"state": self.properties[CONF_STATE], "constrain_enabled": True}

        if self.properties.get(CONF_RUN_ON_DAYS):
            run_on_days(
                self,
                self._on_schedule_toggle,
                self.properties[CONF_RUN_ON_DAYS],
                self.parse_time(self.properties[CONF_SCHEDULE_TIME]),
                auto_constraints=True,
                **kwargs,
            )
        else:
            self.run_daily(
                self._on_schedule_toggle,
                self.parse_time(self.properties[CONF_SCHEDULE_TIME]),
                auto_constraints=True,
                **kwargs,
            )


class ToggleOnEvent(BaseSwitch):
    """Define a feature to toggle a switch when seeing a certain event/payload."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_SWITCH): cv.entity_id}, extra=vol.ALLOW_EXTRA
            ),
            CONF_PROPERTIES: vol.Schema(
                {
                    vol.Required(CONF_STATE): vol.In(TOGGLE_STATES),
                    vol.Required(CONF_EVENT): str,
                    vol.Optional(CONF_EVENT_DATA): dict,
                },
                extra=vol.ALLOW_EXTRA,
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self._on_event_triggered,
            self.properties[CONF_EVENT],
            **self.properties.get(CONF_EVENT_DATA, {}),
            constrain_enabled=True,
        )

    def _on_event_triggered(self, event_name: str, data: dict, kwargs: dict) -> None:
        """React when the method/payload is seen."""
        self.toggle(state=self.properties[CONF_STATE])


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
            self._on_start_cycle,
            self.parse_time(self.properties[CONF_START_TIME]),
            constrain_enabled=True,
        )

        self.run_daily(
            self._on_stop_cycle,
            self.parse_time(self.properties[CONF_END_TIME]),
            constrain_enabled=True,
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


class ToggleOnState(BaseSwitch):
    """Define a feature to toggle the switch when an entity enters a state."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {
                    vol.Required(CONF_SWITCH): cv.entity_id,
                    vol.Required(CONF_TARGET): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            ),
            CONF_PROPERTIES: vol.Schema(
                {
                    vol.Required(CONF_STATE): vol.In(TOGGLE_STATES),
                    vol.Required(CONF_TARGET_STATE): str,
                    vol.Optional(CONF_DELAY): int,
                    vol.Optional(CONF_RETURN_DELAY): int,
                },
                extra=vol.ALLOW_EXTRA,
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_state_change,
            self.entity_ids[CONF_TARGET],
            auto_constraints=True,
            constrain_enabled=True,
        )

    def _on_state_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Toggle the switch depending on the target entity's state."""
        if old == new:
            return

        if new == self.properties[CONF_TARGET_STATE]:
            if CONF_DELAY in self.properties:
                self.handles[HANDLE_TOGGLE_STATE] = self.run_in(
                    self._on_schedule_toggle,
                    self.properties[CONF_DELAY],
                    state=self.properties[CONF_STATE],
                )
            else:
                self.toggle(state=self.properties[CONF_STATE])

            if CONF_RETURN_DELAY in self.properties:
                self.handles[HANDLE_TOGGLE_STATE_RETURN] = self.run_in(
                    self._on_schedule_toggle,
                    self.properties[CONF_RETURN_DELAY],
                    state=self.properties[CONF_STATE],
                    opposite=True,
                )
        else:
            if HANDLE_TOGGLE_STATE in self.handles:
                handle = self.handles.pop(HANDLE_TOGGLE_STATE)
                self.cancel_timer(handle)
            if HANDLE_TOGGLE_STATE_RETURN in self.handles:
                handle = self.handles.pop(HANDLE_TOGGLE_STATE_RETURN)
                self.cancel_timer(handle)


class VacationMode(BaseSwitch):
    """Define a feature to simulate craziness when we're out of town."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_SWITCH): cv.entity_id}, extra=vol.ALLOW_EXTRA
            ),
            CONF_PROPERTIES: vol.Schema(
                {
                    vol.Required(CONF_START_TIME): vol.Any(str, vol.In(SOLAR_EVENTS)),
                    vol.Required(CONF_END_TIME): vol.Any(str, vol.In(SOLAR_EVENTS)),
                },
                extra=vol.ALLOW_EXTRA,
            ),
        }
    )

    def _cancel_automation(self) -> None:
        """Cancel the handle (if it exists)."""
        if HANDLE_VACATION_MODE in self.handles:
            handle = self.handles.pop(HANDLE_VACATION_MODE)
            self.cancel_timer(handle)

    def configure(self) -> None:
        """Configure."""
        self.set_schedule(self.properties[CONF_START_TIME], self._on_start_cycle)
        self.set_schedule(self.properties[CONF_END_TIME], self._on_stop_cycle)

    def _on_start_cycle(self, kwargs: dict) -> None:
        """Start the toggle cycle."""
        self._on_toggle_and_run({"state": "on"})

    def _on_stop_cycle(self, kwargs: dict) -> None:
        """Stop the toggle cycle."""
        self._cancel_automation()
        self.toggle(state="off")

    def _on_toggle_and_run(self, kwargs: dict) -> None:
        """Toggle the swtich and randomize the next toggle."""
        self.toggle(state=kwargs[CONF_STATE])

        if kwargs[CONF_STATE] == "on":
            state = "off"
        else:
            state = "on"

        self.handles[HANDLE_VACATION_MODE] = self.run_in(
            self._on_toggle_and_run, randint(5 * 60, 60 * 60), state=state  # nosec
        )

    def on_disable(self) -> None:
        """Perform steps to cancel the automation if the automation is disabled."""
        self._cancel_automation()

    def set_schedule(self, time: str, handler: Callable, **kwargs) -> None:
        """Set the appropriate schedulers based on the passed in time."""
        if time in ("sunrise", "sunset"):
            method = getattr(self, "run_at_{0}".format(time))
            method(handler, **kwargs, constrain_enabled=True)
        else:
            self.run_daily(
                handler, self.parse_time(time), **kwargs, constrain_enabled=True
            )
