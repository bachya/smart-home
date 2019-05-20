"""Define automations for Home Assistant itself."""
import voluptuous as vol

from const import BLACKOUT_END, BLACKOUT_START, CONF_ENTITY_IDS
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
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

            self.vacation_mode.state = 'on'
        elif (kwargs['action'] == 'off' and self.vacation_mode.state == 'on'):
            self.log('Setting vacation mode to "off"')

            self.vacation_mode.state = 'off'


class BadLoginNotification(Base):
    """Define a feature to notify me of unauthorized login attempts."""

    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_ENTITY_IDS:
            vol.Schema({
                vol.Required(CONF_BAD_LOGIN): cv.entity_id,
                vol.Required(CONF_IP_BAN): cv.entity_id,
            },
                       extra=vol.ALLOW_EXTRA),
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
            self, 'Aaron', new['attributes']['message'], title=title)


class DetectBlackout(Base):
    """Define a feature to manage blackout awareness."""

    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_ENTITY_IDS:
            vol.Schema({
                vol.Required(CONF_BLACKOUT_SWITCH): cv.entity_id,
            },
                       extra=vol.ALLOW_EXTRA),
    })

    def configure(self) -> None:
        """Configure."""
        if self.now_is_between(BLACKOUT_START, BLACKOUT_END):
            self.turn_on(self.entity_ids[CONF_BLACKOUT_SWITCH])
        else:
            self.turn_off(self.entity_ids[CONF_BLACKOUT_SWITCH])

        self.run_daily(
            self.boundary_reached,
            self.parse_time(BLACKOUT_START),
            state='on',
            constrain_input_boolean=self.enabled_entity_id)
        self.run_daily(
            self.boundary_reached,
            self.parse_time(BLACKOUT_END),
            state='off',
            constrain_input_boolean=self.enabled_entity_id)

    def boundary_reached(self, kwargs: dict) -> None:
        """Set the blackout sensor appropriately based on time."""
        self.log('Setting blackout sensor: {0}'.format(kwargs['state']))

        if kwargs['state'] == 'on':
            self.turn_on(self.entity_ids[CONF_BLACKOUT_SWITCH])
        else:
            self.turn_off(self.entity_ids[CONF_BLACKOUT_SWITCH])
