"""Define quick-to-use automations that send notifications."""
from core import Base
from notification import send_notification

EVENT_SEND_NOTIFICATION = "SEND_NOTIFICATION"

CONF_DATA = "data"
CONF_INTERVAL = "interval"
CONF_ITERATIONS = "iterations"
CONF_TITLE = "title"
CONF_WHEN = "when"


class NotificationOnEvent(Base):  # pylint: disable=too-few-public-methods
    """Define an automation that sends notifications on events."""

    def configure(self) -> None:
        """Configure."""
        self.listen_event(self._on_event_received, EVENT_SEND_NOTIFICATION)

    def _on_event_received(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Send a notification."""
        kwargs = {
            CONF_DATA: data.get(CONF_DATA),
            CONF_INTERVAL: data.get(CONF_INTERVAL),
            CONF_ITERATIONS: data.get(CONF_ITERATIONS),
            CONF_TITLE: data.get(CONF_TITLE),
        }
        if CONF_WHEN in data:
            kwargs[CONF_WHEN] = self.parse_datetime(data[CONF_WHEN])

        send_notification(data["targets"], data["message"], **kwargs)
