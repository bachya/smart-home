"""Define automations for Home Assistant itself."""
import voluptuous as vol

from const import CONF_ENTITY_IDS, EVENT_PRESENCE_CHANGE
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from notification import send_notification

CONF_BAD_LOGIN = "bad_login"
CONF_BLACKOUT_SWITCH = "blackout_switch"
CONF_IP_BAN = "ip_ban"


class AutoVacationMode(Base):
    """Define automated alterations to vacation mode."""

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self.presence_changed,
            EVENT_PRESENCE_CHANGE,
            new=self.presence_manager.HomeStates.extended_away.value,
            first=False,
            action="on",
            constrain_enabled=True,
        )
        self.listen_event(
            self.presence_changed,
            EVENT_PRESENCE_CHANGE,
            new=self.presence_manager.HomeStates.just_arrived.value,
            first=True,
            action="off",
            constrain_enabled=True,
        )

    def presence_changed(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Alter Vacation Mode based on presence."""
        if kwargs["action"] == "on" and self.vacation_mode.state == "off":
            self.log('Setting vacation mode to "on"')
            self.vacation_mode.activate()
        elif kwargs["action"] == "off" and self.vacation_mode.state == "on":
            self.log('Setting vacation mode to "off"')
            self.vacation_mode.deactivate()


class BadLoginNotification(Base):
    """Define a feature to notify me of unauthorized login attempts."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {
                    vol.Required(CONF_BAD_LOGIN): cv.entity_id,
                    vol.Required(CONF_IP_BAN): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            )
        }
    )

    def configure(self) -> None:
        """Configure."""
        for notification_type in self.entity_ids.values():
            self.listen_state(
                self._on_bad_login,
                notification_type,
                attribute="all",
                constrain_enabled=True,
            )

    def _on_bad_login(
        self, entity: str, attribute: str, old: str, new: dict, kwargs: dict
    ) -> None:
        """Send a notification when there's a bad login attempt."""
        if not new:
            return

        if entity == self.entity_ids[CONF_BAD_LOGIN]:
            title = "Unauthorized Access Attempt"
        else:
            title = "IP Ban"

        send_notification(
            self, "person:Aaron", new["attributes"]["message"], title=title
        )
