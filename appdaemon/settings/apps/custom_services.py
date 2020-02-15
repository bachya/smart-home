"""Define custom services."""
import voluptuous as vol

from const import (
    CONF_NOTIFICATION_DATA,
    CONF_NOTIFICATION_INTERVAL,
    CONF_NOTIFICATION_ITERATIONS,
    CONF_NOTIFICATION_MESSAGE,
    CONF_NOTIFICATION_TARGET,
    CONF_NOTIFICATION_TITLE,
    CONF_NOTIFICATION_WHEN,
)
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from notification import send_notification

CONF_SERVICE_NAME = "service_name"


class SendNotification(Base):  # pylint: disable=too-few-public-methods
    """Define an automation that sends notifications on events."""

    APP_SCHEMA = APP_SCHEMA.extend({vol.Required(CONF_SERVICE_NAME): cv.string})

    def configure(self) -> None:
        """Configure."""
        self.register_service(
            f"appdaemon/{self.args[CONF_SERVICE_NAME]}", self._service_called
        )

    def _service_called(
        self, namespace: str, domain: str, service: str, data: dict
    ) -> None:
        """Send a notification."""
        kwargs = {
            "data": data.get(CONF_NOTIFICATION_DATA),
            "interval": data.get(CONF_NOTIFICATION_INTERVAL),
            "iterations": data.get(CONF_NOTIFICATION_ITERATIONS),
            "title": data.get(CONF_NOTIFICATION_TITLE),
        }
        if "when" in data:
            kwargs["when"] = self.parse_datetime(data[CONF_NOTIFICATION_WHEN])

        send_notification(
            self,
            data[CONF_NOTIFICATION_TARGET],
            data[CONF_NOTIFICATION_MESSAGE],
            **kwargs,
        )
