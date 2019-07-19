"""Define an automation for handling notifications from events."""
from const import CONF_MESSAGE, CONF_NOTIFICATION_TARGET, CONF_TITLE
from core import Base
from notification import send_notification

DEFAULT_EVENT = "TRIGGER_MESSAGE"


class SendNotification(Base):  # pylint: disable=too-few-public-methods
    """Define a class to send notifications from HASS automation events."""

    def configure(self) -> None:
        """Configure."""
        self.listen_event(self._on_event_receieved, DEFAULT_EVENT)

    def _on_event_receieved(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to the event."""
        kwargs = {}
        if CONF_TITLE in data:
            kwargs[CONF_TITLE] = data[CONF_TITLE]

        send_notification(
            self, data[CONF_NOTIFICATION_TARGET], data[CONF_MESSAGE], **kwargs
        )
