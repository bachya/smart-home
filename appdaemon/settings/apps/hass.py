"""Define automations for Home Assistant itself."""
from typing import Callable, Optional
import voluptuous as vol

from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from notification import send_notification

CONF_BAD_LOGIN = "bad_login"
CONF_BLACKOUT_SWITCH = "blackout_switch"
CONF_IP_BAN = "ip_ban"


class BadLoginNotification(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify me of unauthorized login attempts."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_BAD_LOGIN): cv.entity_id,
            vol.Required(CONF_IP_BAN): cv.entity_id,
        }
    )

    def configure(self) -> None:
        """Configure."""
        self._send_notification_func = None  # type: Optional[Callable]

        for notification_type in self.args.values():
            self.listen_state(self._on_bad_login, notification_type, attribute="all")

    def _on_bad_login(
        self, entity: str, attribute: str, old: str, new: dict, kwargs: dict
    ) -> None:
        """Send a notification when there's a bad login attempt."""
        if not new:
            return

        if entity == self.args[CONF_BAD_LOGIN]:
            title = "Unauthorized Access Attempt"
        else:
            title = "IP Ban"

        def _send_notification() -> None:
            """Send a notification about the attempt."""
            send_notification(
                self, "person:Aaron", new["attributes"]["message"], title=title
            )

        if self.enabled:
            _send_notification()
        else:
            self._send_notification_func = _send_notification

    def on_enable(self) -> None:
        """Send the notification once the automation is enabled."""
        if self._send_notification_func:
            self._send_notification_func()
            self._send_notification_func = None
