"""Define automations for our cars."""
from typing import Union

import voluptuous as vol

from const import (
    CONF_ENTITY_IDS,
    CONF_FRIENDLY_NAME,
    CONF_NOTIFICATION_TARGET,
    CONF_PROPERTIES,
)
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from notification import send_notification

CONF_CAR = "car"
CONF_FUEL_THRESHOLD = "fuel_threshold"

HANDLE_LOW_FUEL = "low_fuel"


class NotifyLowFuel(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify of the vehicle's ETA to home."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_CAR): cv.entity_id}, extra=vol.ALLOW_EXTRA
            ),
            CONF_PROPERTIES: vol.Schema(
                {
                    vol.Required(CONF_FRIENDLY_NAME): str,
                    vol.Required(CONF_FUEL_THRESHOLD): int,
                    vol.Required(CONF_NOTIFICATION_TARGET): str,
                },
                extra=vol.ALLOW_EXTRA,
            ),
        }
    )

    def configure(self):
        """Configure."""
        self.registered = False

        self.listen_state(
            self._on_low_fuel,
            self.entity_ids[CONF_CAR],
            attribute="fuel_level",
            constrain_enabled=True,
        )

    def _on_low_fuel(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Send a notification when my car is low on gas."""
        try:
            if int(new) < self.properties["fuel_threshold"]:
                if self.registered:
                    return

                self.registered = True

                self.log("Low fuel detected detected: %s", self.entity_ids[CONF_CAR])

                send_notification(
                    self,
                    self.properties[CONF_NOTIFICATION_TARGET],
                    "{0} needs gas; fill 'er up!.".format(
                        self.properties[CONF_FRIENDLY_NAME]
                    ),
                    title="{0} is low ⛽".format(self.properties[CONF_FRIENDLY_NAME]),
                )
            else:
                self.registered = False
        except ValueError:
            return
