"""Define automations for our cars."""
from typing import Union

import voluptuous as vol

from const import CONF_FRIENDLY_NAME, CONF_NOTIFICATION_TARGET
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from helpers.notification import send_notification

CONF_CAR = "car"
CONF_FUEL_THRESHOLD = "fuel_threshold"

HANDLE_LOW_FUEL = "low_fuel"


class NotifyLowFuel(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify of the vehicle's ETA to home."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_CAR): cv.entity_id,
            vol.Required(CONF_FRIENDLY_NAME): cv.string,
            vol.Required(CONF_FUEL_THRESHOLD): cv.positive_int,
            vol.Required(CONF_NOTIFICATION_TARGET): cv.notification_target,
        }
    )

    def configure(self):
        """Configure."""
        self.registered = False

        self.listen_state(
            self._on_low_fuel, self.args[CONF_CAR], attribute="fuel_level"
        )

    def _on_low_fuel(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Send a notification when my car is low on gas."""
        try:
            if int(new) < self.args["fuel_threshold"]:
                if self.registered:
                    return

                self.registered = True

                self.log("Low fuel detected detected: %s", self.args[CONF_CAR])

                send_notification(
                    self,
                    self.args[CONF_NOTIFICATION_TARGET],
                    f"{self.args[CONF_FRIENDLY_NAME]} needs gas; fill 'er up!.",
                    title=f"{self.args[CONF_FRIENDLY_NAME]} is low ⛽",
                )
            else:
                self.registered = False
        except ValueError:
            return
