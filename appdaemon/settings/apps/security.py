"""Define automations for security."""
from enum import Enum
from threading import Lock
from typing import Union

import voluptuous as vol

from core import APP_SCHEMA, Base
from const import (
    CONF_FRIENDLY_NAME,
    CONF_STATE,
    EVENT_ALARM_CHANGE,
)
from helpers import config_validation as cv
from helpers.notification import send_notification

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


class PersonDetectedOnCamera(Base):  # pylint: disable=too-few-public-methods
    """Define a feature to react when a person is detected on one or more cameras."""

    def configure(self) -> None:
        """Configure."""
        self._hits = 0
        self._lock = Lock()

        if self.presence_manager.noone(self.presence_manager.HomeStates.home):
            self.enable()
        else:
            self.disable()

        for camera in self.args[CONF_CAMERAS]:
            self.listen_state(
                self._on_detection,
                camera[CONF_PRESENCE_DETECTOR_ENTITY_ID],
                new="on",
                attribute="all",
                camera_entity_id=camera[CONF_CAMERA_ENTITY_ID],
            )

        self.run_every(
            self._on_window_expiration, self.datetime(), self.args[CONF_WINDOW_SECONDS],
        )

    def _on_detection(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Respond to any hit, no matter the duration."""
        with self._lock:
            self._hits += 1
            if self._hits >= self.args[CONF_HIT_THRESHOLD]:
                self._send_and_reset(kwargs[CONF_CAMERA_ENTITY_ID])

    def _on_window_expiration(self, kwargs: dict) -> None:
        """When the window expires, reset the hit count."""
        self._hits = 0

    def _send_and_reset(self, camera_entity_id: str) -> None:
        """Send a notification and reset."""
        camera_friendly_name = self.get_state(
            camera_entity_id, attribute="friendly_name"
        )

        self.log("Person detected on %s while no one was home", camera_friendly_name)

        send_notification(
            self,
            ["person:Aaron", "person:Britt"],
            f"📷 A possible person was detected on the {camera_friendly_name}.",
            title="Security Issue",
            data={
                "attachment": {"content-type": "jpeg"},
                "push": {"category": "camera"},
                "entity_id": camera_entity_id,
            },
        )
        self._hits = 0


class SecurityManager(Base):
    """Define a class to represent the app."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            vol.Required(CONF_ALARM_CONTROL_PANEL): cv.entity_id,
            vol.Required(CONF_GARAGE_DOOR): cv.entity_id,
            vol.Required(CONF_OVERALL_SECURITY_STATUS): cv.entity_id,
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
        return self.AlarmStates(self.get_state(self.args[CONF_ALARM_CONTROL_PANEL]))

    @property
    def secure(self) -> bool:
        """Return whether the house is secure or not."""
        return self.get_state(self.args[CONF_OVERALL_SECURITY_STATUS]) == "Secure"

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_security_system_change, self.args[CONF_ALARM_CONTROL_PANEL]
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

        self.call_service("cover/close_cover", entity_id=self.args[CONF_GARAGE_DOOR])

    def get_insecure_entities(self) -> list:
        """Return a list of insecure entities."""
        return [
            entity[CONF_FRIENDLY_NAME]
            for entity in self.args["secure_status_mapping"]
            if self.get_state(entity["entity_id"]) == entity[CONF_STATE]
        ]

    def open_garage(self) -> None:
        """Open the garage."""
        self.log("Closing the garage door")

        self.call_service("cover.open_cover", entity_id=self.args[CONF_GARAGE_DOOR])

    def set_alarm(self, new: "AlarmStates") -> None:
        """Set the security system."""
        if new == self.AlarmStates.disarmed:
            self.log("Disarming the security system")

            self.call_service(
                "alarm_control_panel/alarm_disarm",
                entity_id=self.args[CONF_ALARM_CONTROL_PANEL],
            )
        elif new in (self.AlarmStates.away, self.AlarmStates.home):
            self.log('Arming the security system: "%s"', new.name)

            self.call_service(
                f'alarm_control_panel/alarm_arm_{new.value.split("_")[1]}',
                entity_id=self.args[CONF_ALARM_CONTROL_PANEL],
            )
        else:
            raise AttributeError(f"Unknown security state: {new}")
