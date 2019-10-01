"""Define automations for various home systems."""
from typing import Callable, List, Optional, Union

import requests
import voluptuous as vol

from core import APP_SCHEMA, Base
from const import (
    CONF_DURATION,
    CONF_ENTITY_ID,
    CONF_ENTITY_IDS,
    CONF_NOTIFICATION_INTERVAL,
    CONF_NOTIFICATION_TARGET,
    CONF_PROPERTIES,
    CONF_STATE,
)
from helpers import config_validation as cv
from notification import send_notification

CONF_AARON_ROUTER_TRACKER = "aaron_router_tracker"

CONF_BATTERIES_TO_MONITOR = "batteries_to_monitor"
CONF_BATTERY_LEVEL_THRESHOLD = "battery_level_threshold"

CONF_EXPIRY_THRESHOLD = "expiry_threshold"

CONF_NEW_STATE = "new_state"
CONF_OLD_STATE = "old_state"

CONF_PI_HOLE_ACTIVE_SENSOR = "pi_hole_active_sensor"
CONF_PI_HOLE_API_KEY = "pi_hole_api_key"
CONF_PI_HOLE_HOSTS = "pi_hole_hosts"
CONF_PI_HOLE_OFF_EVENT = "pi_hole_off_event"
CONF_PI_HOLE_ON_EVENT = "pi_hole_on_event"

HANDLE_BATTERY_LOW = "battery_low"


class AaronAccountability(Base):
    """Define features to keep me accountable on my phone."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_AARON_ROUTER_TRACKER): cv.entity_id},
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_disconnect,
            self.entity_ids[CONF_AARON_ROUTER_TRACKER],
            new="not_home",
            constrain_in_blackout=True,
            constrain_anyone="home",
        )

    @property
    def router_tracker_state(self) -> str:
        """Return the state of Aaron's Unifi tracker."""
        return self.get_state(self.entity_ids[CONF_AARON_ROUTER_TRACKER])

    def _on_disconnect(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Send a notification when I disconnect during a blackout."""
        self._send_notification()

    def _send_notification(self) -> None:
        """Send notification to my love."""
        send_notification(
            self,
            "ios_brittany_bachs_iphone",
            "His phone shouldn't be off wifi during the night.",
            title="Check on Aaron",
        )


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
            if entity.split(".")[0] == "binary_sensor":
                self.listen_state(
                    self._on_battery_change, entity, new="on", attribute="all"
                )
            else:
                self.listen_state(self._on_battery_change, entity, attribute="all")

    def _on_battery_change(
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
            # If the sensor value can't be parsed as an integer, it is either a binary
            # battery sensor or the sensor is unavailable. The former should continue
            # on; the latter should stop immediately:
            if new["state"] != "on":
                return
            value = 0

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
        self._send_notification_func = None  # type: Optional[Callable]

        self.listen_state(
            self._on_limit,
            self.entity_ids[CONF_ENTITY_ID],
            new=self.properties[CONF_STATE],
            duration=self.properties[CONF_DURATION],
        )

    def _on_limit(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Notify when the threshold is reached."""

        def _turn_off() -> None:
            """Turn the entity off."""
            self.turn_off(self.entity_ids[CONF_ENTITY_ID])

        def _send_notification() -> None:
            """Send a notification."""
            message = "The {0} has been left {1} for {2} minutes".format(
                self.get_state(
                    self.entity_ids[CONF_ENTITY_ID], attribute="friendly_name"
                ),
                self.properties[CONF_STATE],
                int(self.properties[CONF_DURATION]) / 60,
            )

            send_notification(self, self.properties[CONF_NOTIFICATION_TARGET], message)

        # If the automation is enabled when a battery is low, send a notification;
        # if not, remember that we should send the notification when the automation
        # becomes enabled:
        if self.enabled:
            _send_notification()
        else:
            self._send_notification_func = _send_notification

    def on_enable(self) -> None:
        """Send the notification once the automation is enabled (if appropriate)."""
        if self._send_notification_func:
            self._send_notification_func()
            self._send_notification_func = None


class NotifyOnStateChange(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to send a notification when an entity(s) changes state."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema({vol.Required(CONF_ENTITY_ID): cv.ensure_list}),
            CONF_PROPERTIES: vol.All(
                vol.Schema(
                    {
                        vol.Required(CONF_NOTIFICATION_TARGET): str,
                        vol.Optional(CONF_NEW_STATE): str,
                        vol.Optional(CONF_OLD_STATE): str,
                        vol.Optional(CONF_DURATION): int,
                    },
                    extra=vol.ALLOW_EXTRA,
                ),
                cv.has_at_least_one_key(CONF_NEW_STATE, CONF_OLD_STATE),
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self._send_notification_func = None  # type: Optional[Callable]

        kwargs = {}
        if CONF_DURATION in self.properties:
            kwargs["duration"] = self.properties[CONF_DURATION]
        if CONF_NEW_STATE in self.properties:
            kwargs["new"] = self.properties[CONF_NEW_STATE]
        if CONF_OLD_STATE in self.properties:
            kwargs["old"] = self.properties[CONF_OLD_STATE]

        for entity in self.entity_ids[CONF_ENTITY_ID]:
            self.listen_state(self._on_state_change, entity, **kwargs)

    def _on_state_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Send a notification when the state has changed."""

        def _send_notification() -> None:
            """Send a notification."""
            send_notification(
                self,
                self.properties[CONF_NOTIFICATION_TARGET],
                "{0} has changed its state: `{1}`.".format(entity, new),
            )

        # If the automation is enabled when a battery is low, send a notification;
        # if not, remember that we should send the notification when the automation
        # becomes enabled:
        if self.enabled:
            _send_notification()
        else:
            self._send_notification_func = _send_notification

    def on_enable(self) -> None:
        """Send the notification once the automation is enabled (if appropriate)."""
        if self._send_notification_func:
            self._send_notification_func()
            self._send_notification_func = None


class PiHoleSwitch(Base):  # pylint: disable=too-few-public-methods
    """Define a switch to turn on/off all Pi-hole instances."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_PI_HOLE_ACTIVE_SENSOR): cv.entity_id},
                extra=vol.ALLOW_EXTRA,
            ),
            CONF_PROPERTIES: vol.Schema(
                {
                    vol.Required(CONF_PI_HOLE_API_KEY): str,
                    vol.Required(CONF_PI_HOLE_HOSTS): list,
                    vol.Required(CONF_PI_HOLE_OFF_EVENT): str,
                    vol.Required(CONF_PI_HOLE_ON_EVENT): str,
                },
                extra=vol.ALLOW_EXTRA,
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        if self._is_enabled:
            self._set_dummy_sensor("on")
        else:
            self._set_dummy_sensor("off")

        self.listen_event(self._on_switch_off, self.properties[CONF_PI_HOLE_OFF_EVENT])
        self.listen_event(self._on_switch_on, self.properties[CONF_PI_HOLE_ON_EVENT])

    @property
    def _is_enabled(self) -> bool:
        """Return whether any Pi-hole hosts are enabled."""
        for host in self.properties[CONF_PI_HOLE_HOSTS]:
            resp = self._request(host, "status")
            status = resp.json()["status"]

            if status == "enabled":
                return True

        return False

    def _on_switch_off(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to the switch being turned off."""
        self.disable_pi_hole()

    def _on_switch_on(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to the switch being turned on."""
        self.enable_pi_hole()

    def _request(self, host: str, endpoint: str) -> requests.Response:
        """Send an HTTP request to Pi-hole."""
        return requests.get(
            "http://{0}/admin/api.php?{1}".format(host, endpoint),
            params={"auth": self.properties[CONF_PI_HOLE_API_KEY]},
        )

    def _set_dummy_sensor(self, state: str) -> None:
        """Set the state of off a dummy sensor which informs the switch's state."""
        self.set_state(
            self.entity_ids[CONF_PI_HOLE_ACTIVE_SENSOR],
            state=state,
            attributes={"friendly_name": "Pi-hole"},
        )

    def disable_pi_hole(self) -> None:
        """Disable Pi-hole."""
        self._set_dummy_sensor("off")
        for host in self.properties[CONF_PI_HOLE_HOSTS]:
            self._request(host, "disable")

    def enable_pi_hole(self) -> None:
        """Enable Pi-hole."""
        self._set_dummy_sensor("on")
        for host in self.properties[CONF_PI_HOLE_HOSTS]:
            self._request(host, "enable")


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
