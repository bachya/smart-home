"""Define automations for health."""
from typing import Union

import voluptuous as vol

from const import CONF_ENTITY_IDS, CONF_PROPERTIES, CONF_UPDATE_INTERVAL
from core import APP_SCHEMA, Base
from helpers import config_validation as cv
from notification import send_notification

CONF_AARON_ROUTER_TRACKER = 'aaron_router_tracker'
CONF_AQI = 'aqi'
CONF_AQI_THRESHOLD = 'aqi_threshold'
CONF_HVAC_STATE = 'hvac_state'


class AaronAccountability(Base):
    """Define features to keep me accountable on my phone."""
    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_ENTITY_IDS: vol.Schema({
            vol.Required(CONF_AARON_ROUTER_TRACKER): cv.entity_id,
        }, extra=vol.ALLOW_EXTRA),
    })

    def configure(self) -> None:
        """Configure."""
        self.run_daily(
            self.send_notification_when_blackout_start,
            self.blackout_mode.blackout_start)

        self.listen_state(
            self.send_notification_on_disconnect,
            self.entity_ids[CONF_AARON_ROUTER_TRACKER],
            new='not_home',
            constrain_in_blackout=True,
            constrain_anyone='home')

    @property
    def router_tracker_state(self) -> str:
        """Return the state of Aaron's Unifi tracker."""
        return self.get_state(self.entity_ids[CONF_AARON_ROUTER_TRACKER])

    def _send_notification(self) -> None:
        """Send notification to my love."""
        send_notification(
            self,
            'ios_brittany_bachs_iphone',
            "His phone shouldn't be off wifi during the night.",
            title='Check on Aaron')

    def send_notification_when_blackout_start(self, kwargs: dict) -> None:
        """Send a notification if offline when blackout starts."""
        if (self.aaron.home_state == self.presence_manager.HomeStates.home
                and self.router_tracker_state == 'not_home'):
            self._send_notification()

    def send_notification_on_disconnect(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Send a notification when I disconnect during a blackout."""
        self._send_notification()


class NotifyBadAqi(Base):
    """Define a feature to notify us of bad air quality."""

    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_ENTITY_IDS: vol.Schema({
            vol.Required(CONF_AQI): cv.entity_id,
            vol.Required(CONF_HVAC_STATE): cv.entity_id,
        }, extra=vol.ALLOW_EXTRA),
        CONF_PROPERTIES: vol.Schema({
            vol.Required(CONF_AQI_THRESHOLD): int,
        }, extra=vol.ALLOW_EXTRA),
    })

    @property
    def current_aqi(self) -> int:
        """Define a property to get the current AQI."""
        return int(self.get_state(self.entity_ids[CONF_AQI]))

    def configure(self) -> None:
        """Configure."""
        self.notification_sent = False

        self.listen_state(
            self.bad_aqi_detected,
            self.entity_ids[CONF_HVAC_STATE],
            new='cooling',
            constrain_input_boolean=self.enabled_entity_id)

    def bad_aqi_detected(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Send select notifications when cooling and poor AQI."""
        if (not self.notification_sent
                and self.current_aqi > self.properties[CONF_AQI_THRESHOLD]):
            self.log('Poor AQI; notifying anyone at home')

            send_notification(
                self,
                'presence:home',
                'AQI is at {0}; consider closing the humidifier vent.'.format(
                    self.current_aqi),
                title='Poor AQI 😤')
            self.notification_sent = True
        elif (self.notification_sent
              and self.current_aqi <= self.properties[CONF_AQI_THRESHOLD]):
            send_notification(
                self,
                'presence:home',
                'AQI is at {0}; open the humidifer vent again.'.format(
                    self.current_aqi),
                title='Better AQI 😅')
            self.notification_sent = True
