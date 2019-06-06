"""Define a mode."""
from datetime import time
from typing import List, Union

import voluptuous as vol

from const import CONF_PROPERTIES
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from helpers.dt import time_is_between

CONF_BLACKOUT_END = "blackout_end"
CONF_BLACKOUT_START = "blackout_start"


class Mode(Base):
    """Define a mode."""

    def configure(self) -> None:
        """Configure."""
        self._enabled_toggles_to_disable = []  # type: List[str]
        self._enabled_toggles_to_enable = []  # type: List[str]
        self._switch = "input_boolean.mode_{0}".format(self.name)

        self.listen_state(self.switch_turned_off_cb, self._switch, new="off")
        self.listen_state(self.switch_turned_on_cb, self._switch, new="on")

    @property
    def state(self) -> str:
        """Return the current state of the mode switch."""
        return self.get_state(self._switch)

    def activate(self) -> None:
        """Activate the mode."""
        self.turn_on(self._switch)

    def deactivate(self) -> None:
        """Deactivate the mode."""
        self.turn_off(self._switch)

    def register_enabled_entity(
        self, enabled_entity_id: str, value: str
    ) -> None:
        """Record how a enable toggle should respond when in this mode."""
        location = getattr(self, "_enabled_toggles_to_{0}".format(value))
        if enabled_entity_id in location:
            return

        location.append(enabled_entity_id)

    def switch_turned_off_cb(
        self,
        entity: Union[str, dict],
        attribute: str,
        old: str,
        new: str,
        kwargs: dict,
    ) -> None:
        """Respond when the mode is turned off."""
        self.log("Deactivating mode: {0}".format(self.name))
        for enabled_toggle in self._enabled_toggles_to_disable:
            self.turn_on(enabled_toggle)
        for enabled_toggle in self._enabled_toggles_to_enable:
            self.turn_off(enabled_toggle)

    def switch_turned_on_cb(
        self,
        entity: Union[str, dict],
        attribute: str,
        old: str,
        new: str,
        kwargs: dict,
    ) -> None:
        """Respond when the mode is turned on."""
        self.log("Activating mode: {0}".format(self.name))
        for enabled_toggle in self._enabled_toggles_to_enable:
            self.turn_on(enabled_toggle)
        for enabled_toggle in self._enabled_toggles_to_disable:
            self.turn_off(enabled_toggle)


class BlackoutMode(Mode):
    """Define a mode for the blackout."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_PROPERTIES: vol.Schema(
                {
                    vol.Required(CONF_BLACKOUT_START): cv.time,
                    vol.Required(CONF_BLACKOUT_END): cv.time,
                },
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        super().configure()

        self.blackout_start = self.parse_time(
            self.properties[CONF_BLACKOUT_START]
        )
        self.blackout_end = self.parse_time(self.properties[CONF_BLACKOUT_END])

        if self.in_blackout():
            self.activate()
        else:
            self.deactivate()

        self.run_daily(self._enter_blackout_cb, self.blackout_start)
        self.run_daily(self._exit_blackout_cb, self.blackout_end)

    def _enter_blackout_cb(self, kwargs: dict) -> None:
        """Activate blackout mode at the right time of day."""
        self.activate()

    def _exit_blackout_cb(self, kwargs: dict) -> None:
        """Deactivate blackout mode at the right time of day."""
        self.deactivate()

    def in_blackout(self, target: time = None) -> bool:
        """Return whether we're in the blackout."""
        kwargs = {}
        if target:
            kwargs["target"] = target
        return time_is_between(
            self.blackout_start, self.blackout_end, **kwargs
        )
