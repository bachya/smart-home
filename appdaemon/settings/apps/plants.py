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
            self._on_moisture_change,
            self.entity_ids["current_moisture"],
            constrain_enabled=True,
        )

    @property
    def current_moisture(self) -> int:
        """Define a property to get the current moisture."""
        return int(self.get_state(self.entity_ids["current_moisture"]))

    def _cancel_notification_cycle(self) -> None:
        """Cancel any active notification."""
        if HANDLE_LOW_MOISTURE in self.handles:
            cancel = self.handles.pop(HANDLE_LOW_MOISTURE)
            cancel()

    def _on_moisture_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Notify when the plant's moisture is low."""
        if not self._low_moisture and int(new) < int(
            self.properties["moisture_threshold"]
        ):
            self.log(
                "Notifying people at home that {0} is low on moisture".format(
                    self.properties[CONF_FRIENDLY_NAME]
                )
            )
            self._start_notification_cycle()
            self._low_moisture = True
        else:
            self._cancel_notification_cycle()
            self._low_moisture = False

    def _start_notification_cycle(self) -> None:
        """Start a repeating notification."""
        self.handles[HANDLE_LOW_MOISTURE] = send_notification(
            self,
            "presence:home",
            "{0} is at {1}% moisture and needs water.".format(
                self.properties[CONF_FRIENDLY_NAME], self.current_moisture
            ),
            title="{0} is Dry 💧".format(self.properties[CONF_FRIENDLY_NAME]),
            when=self.datetime(),
            interval=self.properties[CONF_NOTIFICATION_INTERVAL],
        )

    def on_disable(self) -> None:
        """Stop notifications (as necessary) when the automation is disabled."""
        self._cancel_notification_cycle()

    def on_enable(self) -> None:
        """Start notifications (as necessary) when the automation is enabled."""
        self._start_notification_cycle()
