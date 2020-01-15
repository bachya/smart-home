"""Define automations for plants."""
from typing import Union

import voluptuous as vol

from core import APP_SCHEMA, Base
from const import CONF_FRIENDLY_NAME, CONF_NOTIFICATION_INTERVAL
from helpers import config_validation as cv
from notification import send_notification

CONF_CURRENT_MOISTURE = "current_moisture"
CONF_MOISTURE_THRESHOLD = "moisture_threshold"

HANDLE_LOW_MOISTURE = "low_moisture"


class LowMoisture(Base):
    """Define a feature to notify us of low moisture."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_CURRENT_MOISTURE): cv.entity_id,
            vol.Required(CONF_FRIENDLY_NAME): cv.string,
            vol.Required(CONF_MOISTURE_THRESHOLD): cv.positive_int,
            vol.Required(CONF_NOTIFICATION_INTERVAL): cv.time_period,
        }
    )

    def configure(self) -> None:
        """Configure."""
        self._low_moisture_detected = False

        self.listen_state(self._on_moisture_change, self.args[CONF_CURRENT_MOISTURE])

    @property
    def current_moisture(self) -> int:
        """Define a property to get the current moisture."""
        try:
            return int(self.get_state(self.args[CONF_CURRENT_MOISTURE]))
        except ValueError:
            return 100

    def _cancel_notification_cycle(self) -> None:
        """Cancel any active notification."""
        if HANDLE_LOW_MOISTURE in self.handles:
            cancel = self.handles.pop(HANDLE_LOW_MOISTURE)
            cancel()

    def _on_moisture_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Notify when the plant's moisture is low."""
        if self.enabled and int(new) < self.args[CONF_MOISTURE_THRESHOLD]:
            if self._low_moisture_detected:
                return

            self.log("%s has low moisture", self.args[CONF_FRIENDLY_NAME])
            self._start_notification_cycle()
            self._low_moisture_detected = True
        elif self.enabled and int(new) >= self.args[CONF_MOISTURE_THRESHOLD]:
            if not self._low_moisture_detected:
                return

            self._cancel_notification_cycle()
            self._low_moisture_detected = False

    def _start_notification_cycle(self) -> None:
        """Start a repeating notification."""
        self.handles[HANDLE_LOW_MOISTURE] = send_notification(
            self,
            "presence:home",
            (
                f"{self.args[CONF_FRIENDLY_NAME]} is at {self.current_moisture}% "
                "moisture and needs water."
            ),
            title=f"{self.args[CONF_FRIENDLY_NAME]} is Dry 💧",
            when=self.datetime(),
            interval=self.args[CONF_NOTIFICATION_INTERVAL],
        )

    def on_disable(self) -> None:
        """Stop notifications (as necessary) when the automation is disabled."""
        self._cancel_notification_cycle()

    def on_enable(self) -> None:
        """Start notifications (as necessary) when the automation is enabled."""
        try:
            if self.current_moisture < self.args[CONF_MOISTURE_THRESHOLD]:
                self._start_notification_cycle()
        except TypeError:
            self.error("Can't parse non-integer moisture level")
