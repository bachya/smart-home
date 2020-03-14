"""Define automations for various home systems."""
# pylint: disable=too-few-public-methods
from typing import Callable, List, Optional, Union

import voluptuous as vol
from const import CONF_NOTIFICATION_INTERVAL
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from helpers.notification import send_notification

CONF_AARON_ROUTER_TRACKER = "aaron_router_tracker"
CONF_ENTITIES_TO_MONITOR = "batteries_to_monitor"
CONF_BATTERY_LEVEL_THRESHOLD = "battery_level_threshold"
CONF_DURATION = "duration"
CONF_EXPIRY_THRESHOLD = "expiry_threshold"

HANDLE_BATTERY_LOW = "battery_low"

WARNING_LOG_BLACKLIST = [
    "Disconnected from Home Assistant",
    "HVAC mode support has been disabled",
    "not found in namespace",
]


class AppDaemonLogs(Base):
    """Define a feature to notify us of AppDaemon error/warning logs."""

    def configure(self) -> None:
        """Configure."""
        self.listen_log(self._on_log_found, "ERROR")
        self.listen_log(self._on_log_found, "WARNING")

    def _on_log_found(
        self,
        name: str,
        data: dict,
        level: str,
        log_type: str,
        message: str,
        kwargs: dict,
    ):
        """Log a warning or error log if appropriate."""
        if any(
            blacklisted_string
            for blacklisted_string in WARNING_LOG_BLACKLIST
            if blacklisted_string in message
        ):
            return

        if "Traceback" in message:
            self.call_service(
                "python_script/log",
                level="ERROR",
                message="{0}: {1}".format(name, message),
            )
            return

        self.call_service(
            "python_script/log", level=level, message="{0}: {1}".format(name, message)
        )


class EntityPowerIssues(Base):
    """Define a feature to notify us of low batteries."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITIES_TO_MONITOR): cv.ensure_list,
            vol.Required(CONF_BATTERY_LEVEL_THRESHOLD): cv.positive_int,
            vol.Required(CONF_NOTIFICATION_INTERVAL): vol.All(
                cv.time_period, lambda value: value.seconds
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self._registered = []  # type: List[str]
        self._send_notification_func = None  # type: Optional[Callable]

        for entity in self.args[CONF_ENTITIES_TO_MONITOR]:
            if entity.split(".")[0] == "binary_sensor":
                self.listen_state(
                    self._on_entity_change, entity, new="on", attribute="all"
                )
            else:
                self.listen_state(self._on_entity_change, entity, attribute="all")

    def _on_entity_change(
        self,
        entity: Union[str, dict],
        attribute: str,
        old: str,
        new: dict,
        kwargs: dict,
    ) -> None:
        """Notify whenever an entity has issues."""
        name = new["attributes"]["friendly_name"]

        try:
            value = float(new["state"])
        except ValueError:
            # If we're looking at a binary sensor, hardcode some appropriate numeric
            # values:
            if new["state"] == "unavailable":
                return

            if new["state"] == "on":
                value = 100
            else:
                value = 0

        notification_handle = f"{HANDLE_BATTERY_LOW}_{name}"

        def _send_notification():
            """Send the notification."""
            self.data[notification_handle] = send_notification(
                self,
                "slack",
                f"{name} is offline or has a low battery.",
                when=self.datetime(),
                interval=self.args[CONF_NOTIFICATION_INTERVAL],
            )

        if value < self.args[CONF_BATTERY_LEVEL_THRESHOLD]:
            # If we've already registered that the battery is low, don't repeatedly
            # register it:
            if name in self._registered:
                return

            self.log(f"Entity power issue detected: {name}")
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
                if notification_handle in self.data:
                    cancel = self.data.pop(notification_handle)
                    cancel()
            except ValueError:
                return

    def on_enable(self) -> None:
        """Send the notification once the automation is enabled (if appropriate)."""
        if self._send_notification_func:
            self._send_notification_func()
            self._send_notification_func = None


class NotifyOfDeadZwaveDevices(Base):
    """Define a feature to notify me of dead Z-Wave devices."""

    def configure(self) -> None:
        """Configure."""
        for entity_id in self.get_state("zwave").keys():
            self.listen_state(
                self._on_dead_device_found, entity_id, new="dead",
            )

    def _on_dead_device_found(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """React when a dead device is found."""
        send_notification(self, "person:Aaron", f"A Z-Wave device just died: {entity}")


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
            if k not in self.args["to_exclude"]
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
