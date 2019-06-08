"""Define automations for plants."""
from typing import Union

import voluptuous as vol

from core import APP_SCHEMA, Base
from const import (
    CONF_ENTITY_IDS,
    CONF_FRIENDLY_NAME,
    CONF_NOTIFICATION_INTERVAL,
    CONF_PROPERTIES,
)
from helpers import config_validation as cv
from notification import send_notification

CONF_CURRENT_MOISTURE = "current_moisture"
CONF_MOISTURE_THRESHOLD = "moisture_threshold"

HANDLE_LOW_MOISTURE = "low_moisture"


class LowMoisture(Base):
    """Define a feature to notify us of low moisture."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_CURRENT_MOISTURE): cv.entity_id},
                extra=vol.ALLOW_EXTRA,
            ),
            CONF_PROPERTIES: vol.Schema(
                {
                    vol.Required(CONF_FRIENDLY_NAME): str,
                    vol.Required(CONF_MOISTURE_THRESHOLD): int,
                    vol.Required(CONF_NOTIFICATION_INTERVAL): int,
                },
                extra=vol.ALLOW_EXTRA,
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self._low_moisture = False

        self.listen_state(
            self._on_low_moisture,
            self.entity_ids["current_moisture"],
            constrain_enabled=True,
        )

    @property
    def current_moisture(self) -> int:
        """Define a property to get the current moisture."""
        return int(self.get_state(self.entity_ids["current_moisture"]))

    def _on_low_moisture(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Notify when the plant's moisture is low."""
        if not self._low_moisture and int(new) < int(
            self.properties["moisture_threshold"]
        ):
            self.log("Notifying people at home that plant is low on moisture")

            self._low_moisture = True
            self.handles[HANDLE_LOW_MOISTURE] = send_notification(
                self,
                "presence:home",
                "{0} is at {1}% moisture and needs water.".format(
                    self.properties["friendly_name"], self.current_moisture
                ),
                title="{0} is Dry 💧".format(self.properties["friendly_name"]),
                when=self.datetime(),
                interval=self.properties[CONF_NOTIFICATION_INTERVAL],
            )
        else:
            self._low_moisture = False
            if HANDLE_LOW_MOISTURE in self.handles:
                cancel = self.handles.pop(HANDLE_LOW_MOISTURE)
                cancel()
