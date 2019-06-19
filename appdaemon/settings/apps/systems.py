"""Define automations for various home systems."""
from typing import Callable, List, Optional, Union

import voluptuous as vol

from core import APP_SCHEMA, Base
from const import (
    CONF_DURATION,
    CONF_ENTITY_ID,
    CONF_ENTITY_IDS,
    CONF_NOTIFICATION_INTERVAL,
    CONF_PROPERTIES,
    CONF_STATE,
)
from helpers import config_validation as cv
from notification import send_notification

CONF_BATTERIES_TO_MONITOR = "batteries_to_monitor"
CONF_BATTERY_LEVEL_THRESHOLD = "battery_level_threshold"
CONF_EXPIRY_THRESHOLD = "expiry_threshold"
CONF_SSL_EXPIRY = "ssl_expiry"

HANDLE_BATTERY_LOW = "battery_low"


class LowBatteries(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify us of low batteries."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_BATTERIES_TO_MONITOR): cv.ensure_list},
                extra=vol.ALLOW_EXTRA,
            ),
            CONF_PROPERTIES: vol.Schema(
                {
                    vol.Required(CONF_BATTERY_LEVEL_THRESHOLD): int,
                    vol.Required(CONF_NOTIFICATION_INTERVAL): int,
                },
                extra=vol.ALLOW_EXTRA,
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self._registered = []  # type: List[str]
        self._send_notification_func = None  # type: Optional[Callable]

        for entity in self.entity_ids[CONF_BATTERIES_TO_MONITOR]:
            self.listen_state(
                self._on_low_battery, entity, attribute="all", constrain_enabled=True
            )

    def _on_low_battery(
        self,
        entity: Union[str, dict],
        attribute: str,
        old: str,
        new: dict,
        kwargs: dict,
    ) -> None:
        """Create OmniFocus todos whenever there's a low battery."""
        name = new["attributes"]["friendly_name"]

        try:
            value = int(new["state"])
        except ValueError:
            return

        notification_handle = "{0}_{1}".format(HANDLE_BATTERY_LOW, name)

        def _send_notification():
            """Send the notification."""
            self.handles[notification_handle] = send_notification(
                self,
                "slack",
                "{0} has low batteries ({1}%). Replace them ASAP!".format(name, value),
                when=self.datetime(),
                interval=self.properties[CONF_NOTIFICATION_INTERVAL],
            )

        if value < self.properties[CONF_BATTERY_LEVEL_THRESHOLD]:
            # If we've already registered that the battery is low, don't repeatedly
            # register it:
            if name in self._registered:
                return

            self.log("Low battery detected: {0}".format(name))
            self._registered.append(name)

            # If the automation is enabled when a battery is low, send a notification;
            # if not, remember that we should send the notification when the automation
            # becomes enabled:
            if self.enabled:
                _send_notification()
            else:
                self._send_notification_func = _send_notification
        else:
            try:
                self._registered.remove(name)
                self._send_notification_func = None
                if notification_handle in self.handles:
                    cancel = self.handles.pop(notification_handle)
                    cancel()
            except ValueError:
                return

    def on_enable(self) -> None:
        """Send the notification once the automation is enabled (if appropriate)."""
        if self._send_notification_func:
            self._send_notification_func()
            self._send_notification_func = None


class LeftInState(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to monitor whether an entity is left in a state."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_ENTITY_ID): cv.entity_id}, extra=vol.ALLOW_EXTRA
            ),
            CONF_PROPERTIES: vol.Schema(
                {vol.Required(CONF_DURATION): int, vol.Required(CONF_STATE): str},
                extra=vol.ALLOW_EXTRA,
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_limit,
            self.entity_ids[CONF_ENTITY_ID],
            new=self.properties[CONF_STATE],
            duration=self.properties[CONF_DURATION],
            constrain_enabled=True,
        )

    def _on_limit(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Notify when the threshold is reached."""

        def turn_off():
            """Turn the entity off."""
            self.turn_off(self.entity_ids[CONF_ENTITY_ID])

        self.slack_app_home_assistant.ask(
            "The {0} has been left {1} for {2} minutes. Turn it off?".format(
                self.get_state(
                    self.entity_ids[CONF_ENTITY_ID], attribute="friendly_name"
                ),
                self.properties[CONF_STATE],
                int(self.properties[CONF_DURATION]) / 60,
            ),
            {
                "Yes": {
                    "callback": turn_off,
                    "response_text": "You got it; turning it off now.",
                },
                "No": {"response_text": "Keep devouring electricity, little guy."},
            },
        )


class SslExpiration(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify me when the SSL cert is expiring."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_SSL_EXPIRY): cv.entity_id}, extra=vol.ALLOW_EXTRA
            ),
            CONF_PROPERTIES: vol.Schema(
                {vol.Required(CONF_EXPIRY_THRESHOLD): int}, extra=vol.ALLOW_EXTRA
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_expiration_near,
            self.entity_ids[CONF_SSL_EXPIRY],
            constrain_enabled=True,
        )

    def _on_expiration_near(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """When SSL is about to expire, make an OmniFocus todo."""
        if int(new) < self.properties[CONF_EXPIRY_THRESHOLD]:
            self.log("SSL certificate about to expire: {0} days".format(new))

            send_notification(
                self, "slack:@aaron", "SSL expires in less than {0} days".format(new)
            )


class StartHomeKitOnZwaveReady(Base):
    """Define a feature to start HomeKit when the Z-Wave network is ready."""

    def configure(self) -> None:
        """Configure."""
        self._on_scan({})

    @property
    def network_ready(self) -> bool:
        """Return whether the Z-Wave network is ready."""
        zwave_devices = [
            v
            for k, v in self.get_state("zwave").items()
            if k not in self.entity_ids["to_exclude"]
        ]
        for attrs in zwave_devices:
            try:
                if attrs["state"] != "ready":
                    return False
            except TypeError:
                return False
        return True

    def _on_scan(self, kwargs: dict) -> None:
        """Start the _on_scanning process."""
        if self.network_ready:
            self.log("Z-Wave network is ready for HomeKit to start")
            self.call_service("homekit/start")
            return

        self.run_in(self._on_scan, 60)
