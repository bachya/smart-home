"""Define custom services."""
from typing import List

import helpers.config_validation as cv
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
from notification import send_notification


class SendNotification(Base):  # pylint: disable=too-few-public-methods
    """Define an automation that sends notifications on events."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_NOTIFICATION_TARGET): vol.Any(
                cv.notification_target, List[cv.notification_target]
            ),
            vol.Required(CONF_NOTIFICATION_MESSAGE): cv.string,
            vol.Optional(CONF_NOTIFICATION_TITLE): cv.string,
            vol.Optional(CONF_NOTIFICATION_WHEN): cv.string,
            vol.Optional(CONF_NOTIFICATION_INTERVAL): cv.positive_int,
            vol.Optional(CONF_NOTIFICATION_ITERATIONS): cv.positive_int,
            vol.Optional(CONF_NOTIFICATION_DATA): dict,
        }
    )

    SERVICE = "appdaemon/send_notification"

    def configure(self) -> None:
        """Configure."""
        # We'll use this class multiple times, but only want to register the service
        # one time:
        if self.SERVICE not in self.list_services():
            self.register_service(self.SERVICE, self._send_notification)

    def _send_notification(self) -> None:
        """Send a notification."""
        kwargs = {
            CONF_NOTIFICATION_DATA: self.args.get(CONF_NOTIFICATION_DATA),
            CONF_NOTIFICATION_INTERVAL: self.args.get(CONF_NOTIFICATION_INTERVAL),
            CONF_NOTIFICATION_ITERATIONS: self.args.get(CONF_NOTIFICATION_ITERATIONS),
            CONF_NOTIFICATION_TITLE: self.args.get(CONF_NOTIFICATION_TITLE),
        }
        if CONF_NOTIFICATION_WHEN in self.args:
            kwargs[CONF_NOTIFICATION_WHEN] = self.parse_datetime(
                self.args[CONF_NOTIFICATION_WHEN]
            )

        send_notification(
            self.args[CONF_NOTIFICATION_TARGET],
            self.args[CONF_NOTIFICATION_MESSAGE],
            **kwargs,
        )
