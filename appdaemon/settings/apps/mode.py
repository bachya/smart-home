"""Define a mode."""
from datetime import time

import voluptuous as vol

from const import CONF_PROPERTIES, EVENT_MODE_CHANGE
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from helpers.dt import time_is_between

CONF_BLACKOUT_END = "blackout_end"
CONF_BLACKOUT_START = "blackout_start"


class Mode(Base):
    """Define a mode."""

    def configure(self) -> None:
        """Configure."""
        self._switch = "input_boolean.mode_{0}".format(self.name)

    @property
    def state(self) -> str:
        """Return the current state of the mode switch."""
        return self.get_state(self._switch)

    def activate(self) -> None:
        """Activate the mode."""
        self.log("Activating mode: {0}".format(self.name))
        self.turn_on(self._switch)
        self.fire_event(EVENT_MODE_CHANGE, name=self.name, state="on")

    def deactivate(self) -> None:
        """Deactivate the mode."""
        self.log("Deactivating mode: {0}".format(self.name))
        self.turn_off(self._switch)
        self.fire_event(EVENT_MODE_CHANGE, name=self.name, state="off")


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

        self.blackout_start = self.parse_time(self.properties[CONF_BLACKOUT_START])
        self.blackout_end = self.parse_time(self.properties[CONF_BLACKOUT_END])

        if self.in_blackout():
            self.activate()
        else:
            self.deactivate()

        self.run_daily(self._on_blackout_start, self.blackout_start)
        self.run_daily(self._on_blackout_end, self.blackout_end)

    def _on_blackout_end(self, kwargs: dict) -> None:
        """Deactivate blackout mode at the right time of day."""
        self.deactivate()

    def _on_blackout_start(self, kwargs: dict) -> None:
        """Activate blackout mode at the right time of day."""
        self.activate()

    def in_blackout(self, target: time = None) -> bool:
        """Return whether we're in the blackout."""
        kwargs = {}
        if target:
            kwargs["target"] = target
        return time_is_between(self.blackout_start, self.blackout_end, **kwargs)
