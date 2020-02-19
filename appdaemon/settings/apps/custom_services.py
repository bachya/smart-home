"""Define custom services."""
from const import (
    CONF_NOTIFICATION_DATA,
    CONF_NOTIFICATION_INTERVAL,
    CONF_NOTIFICATION_ITERATIONS,
    CONF_NOTIFICATION_MESSAGE,
    CONF_NOTIFICATION_TARGET,
    CONF_NOTIFICATION_TITLE,
    CONF_NOTIFICATION_WHEN,
)
from core import Base
from notification import send_notification

CONF_SERVICE_NAME = "service_name"


class Notifications(Base):  # pylint: disable=too-few-public-methods
    """Define an automation that sends notifications on events."""

    def configure(self) -> None:
        """Configure."""
        self.register_service(
            f"appdaemon/send_notification", self._send_notification_service_called
        )

    def _send_notification_service_called(
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
