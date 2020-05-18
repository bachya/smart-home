"""Define automations for various home systems."""
# pylint: disable=too-few-public-methods
from typing import Union

from core import Base
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
