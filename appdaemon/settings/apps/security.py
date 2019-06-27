"""Define automations for security."""
from datetime import time
from enum import Enum
from typing import Callable, Optional, Union

import voluptuous as vol

from core import APP_SCHEMA, Base
from const import (
    CONF_ENTITY_IDS,
    CONF_FRIENDLY_NAME,
    CONF_NOTIFICATION_INTERVAL,
    CONF_PROPERTIES,
    CONF_STATE,
    EVENT_ALARM_CHANGE,
    EVENT_PROXIMITY_CHANGE,
)
from helpers import config_validation as cv
from notification import send_notification

CONF_ALARM_CONTROL_PANEL = "alarm_control_panel"
CONF_CAMERAS = "cameras"
CONF_CAMERA_ENTITY_ID = "camera_entity_id"
CONF_GARAGE_DOOR = "garage_door"
CONF_HIT_THRESHOLD = "hit_threshold"
CONF_OVERALL_SECURITY_STATUS = "overall_security_status_sensor"
CONF_PRESENCE_DETECTOR_ENTITY_ID = "presence_detector_entity_id"
CONF_TIME_LEFT_OPEN = "time_left_open"
CONF_WINDOW_SECONDS = "window_seconds"

HANDLE_GARAGE_OPEN = "garage_open"


class AbsentInsecure(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify us when we've left home insecure."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_STATE): cv.entity_id}, extra=vol.ALLOW_EXTRA
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        self._send_notification_func = None  # type: Optional[Callable]

        self.listen_state(
            self._on_house_insecure,
            self.entity_ids[CONF_STATE],
            new="Open",
            duration=60 * 5,
            constrain_enabled=True,
            constrain_noone="just_arrived,home",
        )

    def _on_house_insecure(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Send notifications when the house has been left insecure."""

        def _send_notification() -> None:
            """Send the notification."""
            send_notification(
                self,
                ["person:Aaron", "person:Britt"],
                "No one is home and the house isn't locked up.",
                title="Security Issue 🔐",
                data={"push": {"category": "dishwasher"}},
            )

        self.log("No one home and house is insecure; notifying")

        # If the automation is enabled when the house is insecure, send a notification;
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


class AutoDepartureLockup(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to automatically lock up when we leave."""

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self._on_everyone_gone, EVENT_PROXIMITY_CHANGE, constrain_enabled=True
        )

    def _on_everyone_gone(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to 'PROXIMITY_CHANGE' events."""
        if (
            not self.security_manager.secure
            and data["old"] == self.presence_manager.ProximityStates.home.value
            and data["new"] != self.presence_manager.ProximityStates.home.value
        ):
            self.log("Everyone has left; locking up")

            self.turn_on("scene.depart_home")


class AutoNighttimeLockup(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to automatically lock up at night."""

    def configure(self) -> None:
        """Configure."""
        self.run_daily(
            self._on_midnight_reached,
            time(0, 0, 0),
            constrain_enabled=True,
            constrain_anyone="home",
        )

    def _on_midnight_reached(self, kwargs: dict) -> None:
        """Lock up the house at _on_midnight_reached."""
        self.log('Activating "Good Night"')

        self.call_service("scene/turn_on", entity_id="scene.good_night")


class GarageLeftOpen(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify us when the garage is left open."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_GARAGE_DOOR): cv.entity_id}, extra=vol.ALLOW_EXTRA
            ),
            CONF_PROPERTIES: vol.Schema(
                {
                    vol.Required(CONF_NOTIFICATION_INTERVAL): int,
                    vol.Required(CONF_TIME_LEFT_OPEN): int,
                },
                extra=vol.ALLOW_EXTRA,
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_closed, self.entity_ids[CONF_GARAGE_DOOR], new="closed"
        )
        self.listen_state(
            self._on_left_open,
            self.entity_ids[CONF_GARAGE_DOOR],
            new="open",
            duration=self.properties[CONF_TIME_LEFT_OPEN],
        )

    def _cancel_notification_cycle(self) -> None:
        """Cancel any active notification."""
        if HANDLE_GARAGE_OPEN in self.handles:
            cancel = self.handles.pop(HANDLE_GARAGE_OPEN)
            cancel()

    def _on_closed(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Cancel notification when the garage is _on_closed."""
        self._cancel_notification_cycle()

    def _on_left_open(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Send notifications when the garage has been left open."""
        if self.enabled:
            self._start_notification_cycle()
        else:
            self._cancel_notification_cycle()

    def _start_notification_cycle(self) -> None:
        """Start the notification cycle."""
        message = "The garage has been left open. Want to close it?"

        self.handles[HANDLE_GARAGE_OPEN] = send_notification(
            self,
            ["person:Aaron", "person:Britt"],
            message,
            title="Garage Open 🚗",
            when=self.datetime(),
            interval=self.properties[CONF_NOTIFICATION_INTERVAL],
            data={"push": {"category": "garage"}},
        )

        self.slack_app_home_assistant.ask(
            message,
            {
                "Yes": {
                    "callback": self.security_manager.close_garage,
                    "response_text": "You got it; closing it now.",
                },
                "No": {"response_text": "If you really say so..."},
            },
            urgent=True,
        )

    def on_disable(self) -> None:
        """Stop the notification once the automation is disable."""
        self._cancel_notification_cycle()

    def on_enable(self) -> None:
        """Send the notification once the automation is enabled."""
        if self.get_state(self.entity_ids[CONF_GARAGE_DOOR]) == "open":
            self._start_notification_cycle()


class NotifyOnChange(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to notify us the secure status changes."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_STATE): cv.entity_id}, extra=vol.ALLOW_EXTRA
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        self._send_notification_func = None  # type: Optional[Callable]

        self.listen_state(self._on_security_system_change, self.entity_ids[CONF_STATE])

    def _on_security_system_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Send a notification when the security state changes."""

        def _send_notification() -> None:
            """Send the notification."""
            send_notification(
                self,
                ["person:Aaron", "person:Britt"],
                'The security status has changed to "{0}"'.format(new),
                title="Security Change 🔐",
            )

        self.log("Notifying of security status change: {0}".format(new))

        # If the automation is enabled when the state changes, send a notification;
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


class PersonDetectedOnCamera(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to react when a person is detected on one or more cameras."""

    def configure(self) -> None:
        """Configure."""
        if self.presence_manager.noone(self.presence_manager.HomeStates.home):
            self.enable()
        else:
            self.disable()

        self.hits = 0

        self.run_every(
            self._on_window_expiration,
            self.datetime(),
            self.properties[CONF_WINDOW_SECONDS],
            constrain_enabled=True,
        )

        for camera in self.entity_ids[CONF_CAMERAS]:
            self.listen_state(
                self._on_detection,
                camera[CONF_PRESENCE_DETECTOR_ENTITY_ID],
                new="on",
                attribute="all",
                constrain_enabled=True,
                camera_entity_id=camera[CONF_CAMERA_ENTITY_ID],
            )
            self.listen_state(
                self._on_long_detection,
                camera[CONF_PRESENCE_DETECTOR_ENTITY_ID],
                new="on",
                attribute="all",
                duration=self.properties[CONF_WINDOW_SECONDS],
                constrain_enabled=True,
                camera_entity_id=camera[CONF_CAMERA_ENTITY_ID],
            )

    def _on_detection(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Respond to any hit, no matter the duration."""
        self.hits += 1
        if self.hits >= self.properties[CONF_HIT_THRESHOLD]:
            self._send_and_reset(kwargs[CONF_CAMERA_ENTITY_ID])

    def _on_long_detection(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Respond to a longer hit (i.e., one that has lasted for the window)."""
        self._send_and_reset(kwargs[CONF_CAMERA_ENTITY_ID])

    def _on_window_expiration(self, kwargs: dict) -> None:
        """When the window expires, reset the hit count."""
        self.hits = 0

    def _send_and_reset(self, camera_entity_id: str) -> None:
        """Send a notification and reset."""
        camera_friendly_name = self.get_state(
            camera_entity_id, attribute="friendly_name"
        )
        self.log(
            "Person detected on {0} while no one was home".format(camera_friendly_name)
        )
        send_notification(
            self,
            ["person:Aaron", "person:Britt"],
            "A possible person was detected on the {0}.".format(camera_friendly_name),
            title="Security Issue 🔐",
            data={
                "attachment": {"content-type": "jpeg"},
                "push": {"category": "camera"},
                "entity_id": camera_entity_id,
            },
        )
        self.hits = 0


class SecurityManager(Base):
    """Define a class to represent the app."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {
                    vol.Required(CONF_ALARM_CONTROL_PANEL): cv.entity_id,
                    vol.Required(CONF_GARAGE_DOOR): cv.entity_id,
                    vol.Required(CONF_OVERALL_SECURITY_STATUS): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    class AlarmStates(Enum):
        """Define an enum for alarm states."""

        away = "armed_away"
        disarmed = "disarmed"
        home = "armed_home"

    @property
    def alarm_state(self) -> "AlarmStates":
        """Return the current state of the security system."""
        return self.AlarmStates(
            self.get_state(self.entity_ids[CONF_ALARM_CONTROL_PANEL])
        )

    @property
    def secure(self) -> bool:
        """Return whether the house is secure or not."""
        return self.get_state(self.entity_ids[CONF_OVERALL_SECURITY_STATUS]) == "Secure"

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_security_system_change, self.entity_ids[CONF_ALARM_CONTROL_PANEL]
        )

    def _on_security_system_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Fire events when the security system status changes."""
        if new != "unknown":
            self.fire_event(EVENT_ALARM_CHANGE, state=new)

    def close_garage(self) -> None:
        """Close the garage."""
        self.log("Closing the garage door")

        self.call_service(
            "cover/close_cover", entity_id=self.entity_ids[CONF_GARAGE_DOOR]
        )

    def get_insecure_entities(self) -> list:
        """Return a list of insecure entities."""
        return [
            entity[CONF_FRIENDLY_NAME]
            for entity in self.properties["secure_status_mapping"]
            if self.get_state(entity["entity_id"]) == entity[CONF_STATE]
        ]

    def open_garage(self) -> None:
        """Open the garage."""
        self.log("Closing the garage door")

        self.call_service(
            "cover.open_cover", entity_id=self.entity_ids[CONF_GARAGE_DOOR]
        )

    def set_alarm(self, new: "AlarmStates") -> None:
        """Set the security system."""
        if new == self.AlarmStates.disarmed:
            self.log("Disarming the security system")

            self.call_service(
                "alarm_control_panel/alarm_disarm",
                entity_id=self.entity_ids[CONF_ALARM_CONTROL_PANEL],
            )
        elif new in (self.AlarmStates.away, self.AlarmStates.home):
            self.log('Arming the security system: "{0}"'.format(new.name))

            self.call_service(
                "alarm_control_panel/alarm_arm_{0}".format(new.value.split("_")[1]),
                entity_id=self.entity_ids[CONF_ALARM_CONTROL_PANEL],
            )
        else:
            raise AttributeError("Unknown security state: {0}".format(new))
