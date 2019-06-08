"""Define automations for security."""
from datetime import time
from enum import Enum
from typing import Union

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
CONF_GARAGE_DOOR = "garage_door"
CONF_OVERALL_SECURITY_STATUS = "overall_security_status_sensor"
CONF_TIME_LEFT_OPEN = "time_left_open"

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
        self.log("No one home and house is insecure; notifying")

        send_notification(
            self,
            ["person:Aaron", "person:Britt"],
            "No one is home and the house isn't locked up.",
            title="Security Issue 🔐",
            data={"push": {"category": "dishwasher"}},
        )


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
            self._on_closed,
            self.entity_ids[CONF_GARAGE_DOOR],
            new="_on_closed",
            constrain_enabled=True,
        )
        self.listen_state(
            self._on_left_open,
            self.entity_ids[CONF_GARAGE_DOOR],
            new="open",
            duration=self.properties[CONF_TIME_LEFT_OPEN],
            constrain_enabled=True,
        )

    def _on_closed(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Cancel notification when the garage is _on_closed."""
        if HANDLE_GARAGE_OPEN in self.handles:
            self.handles.pop(HANDLE_GARAGE_OPEN)()  # type: ignore

    def _on_left_open(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Send notifications when the garage has been left open."""
        message = "The garage has been left open. Want to close it?"

        self.handles[HANDLE_GARAGE_OPEN] = send_notification(
            self,
            ["person:Aaron", "person:Britt"],
            "The garage has been left open. Want to close it?",
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
        self.listen_state(
            self._on_security_system_change,
            self.entity_ids[CONF_STATE],
            constrain_enabled=True,
        )

    def _on_security_system_change(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Send a notification when the security state changes."""
        self.log("Notifying of security status change: {0}".format(new))

        send_notification(
            self,
            ["person:Aaron", "person:Britt"],
            'The security status has changed to "{0}"'.format(new),
            title="Security Change 🔐",
        )


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
