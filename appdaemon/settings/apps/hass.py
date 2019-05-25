"""Define automations for Home Assistant itself."""
import voluptuous as vol

from const import CONF_ENTITY_IDS
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from helpers.dt import (
    DEFAULT_BLACKOUT_END, DEFAULT_BLACKOUT_START, in_blackout)
from notification import send_notification

CONF_BAD_LOGIN = 'bad_login'
CONF_BLACKOUT_SWITCH = 'blackout_switch'
CONF_IP_BAN = 'ip_ban'


class AutoVacationMode(Base):
    """Define automated alterations to vacation mode."""

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self.presence_changed,
            'PRESENCE_CHANGE',
            new=self.presence_manager.HomeStates.extended_away.value,
            first=False,
            action='on',
            constrain_input_boolean=self.enabled_entity_id)
        self.listen_event(
            self.presence_changed,
            'PRESENCE_CHANGE',
            new=self.presence_manager.HomeStates.just_arrived.value,
            first=True,
            action='off',
            constrain_input_boolean=self.enabled_entity_id)

    def presence_changed(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Alter Vacation Mode based on presence."""
        if (kwargs['action'] == 'on' and self.vacation_mode.state == 'off'):
            self.log('Setting vacation mode to "on"')
            self.vacation_mode.activate()
        elif (kwargs['action'] == 'off' and self.vacation_mode.state == 'on'):
            self.log('Setting vacation mode to "off"')
            self.vacation_mode.deactivate()


class BadLoginNotification(Base):
    """Define a feature to notify me of unauthorized login attempts."""

    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_ENTITY_IDS: vol.Schema({
            vol.Required(CONF_BAD_LOGIN): cv.entity_id,
            vol.Required(CONF_IP_BAN): cv.entity_id,
        }, extra=vol.ALLOW_EXTRA),
    })

    def configure(self) -> None:
        """Configure."""
        for notification_type in self.entity_ids.values():
            self.listen_state(
                self.send_alert,
                notification_type,
                attribute='all',
                constrain_input_boolean=self.enabled_entity_id)

    def send_alert(
            self, entity: str, attribute: str, old: str, new: dict,
            kwargs: dict) -> None:
        """Send a notification when there's a bad login attempt."""
        if not new:
            return

        if entity == self.entity_ids[CONF_BAD_LOGIN]:
            title = 'Unauthorized Access Attempt'
        else:
            title = 'IP Ban'

        send_notification(
            self, 'person:Aaron', new['attributes']['message'], title=title)


class DetectBlackout(Base):
    """Define a feature to manage blackout awareness."""

    def configure(self) -> None:
        """Configure."""
        if in_blackout():
            self.blackout_mode.activate()
        else:
            self.blackout_mode.deactivate()

        self.run_daily(
            self.enter_blackout_cb,
            DEFAULT_BLACKOUT_START,
            constrain_input_boolean=self.enabled_entity_id)
        self.run_daily(
            self.exit_blackout_cb,
            DEFAULT_BLACKOUT_END,
            constrain_input_boolean=self.enabled_entity_id)

    def enter_blackout_cb(self, kwargs: dict) -> None:
        """Activate blackout mode at the right time of day."""
        self.log('Activating blackout mode')
        self.blackout_mode.activate()

    def exit_blackout_cb(self, kwargs: dict) -> None:
        """Deactivate blackout mode at the right time of day."""
        self.log('Deactivating blackout mode')
        self.blackout_mode.deactivate()
