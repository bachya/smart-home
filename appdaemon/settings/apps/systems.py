"""Define automations for various home systems."""
from typing import Union

import voluptuous as vol

from core import APP_SCHEMA, Base
from const import (
    CONF_DURATION, CONF_ENTITY, CONF_ENTITY_IDS, CONF_NOTIFICATION_INTERVAL,
    CONF_PROPERTIES, CONF_STATE, TOGGLE_STATES)
from helpers import config_validation as cv
from notification import send_notification

CONF_BATTERIES_TO_MONITOR = 'batteries_to_monitor'
CONF_BATTERY_LEVEL_THRESHOLD = 'battery_level_threshold'
CONF_EXPIRY_THRESHOLD = 'expiry_threshold'
CONF_SSL_EXPIRY = 'ssl_expiry'

HANDLE_BATTERY_LOW = 'battery_low'


class LowBatteries(Base):
    """Define a feature to notify us of low batteries."""

    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_ENTITY_IDS: vol.Schema({
            vol.Required(CONF_BATTERIES_TO_MONITOR): cv.ensure_list,
        }, extra=vol.ALLOW_EXTRA),
        CONF_PROPERTIES: vol.Schema({
            vol.Required(CONF_BATTERY_LEVEL_THRESHOLD): int,
            vol.Required(CONF_NOTIFICATION_INTERVAL): int,
        }, extra=vol.ALLOW_EXTRA),
    })

    def configure(self) -> None:
        """Configure."""
        self._registered = []  # type: ignore
        self.handles[HANDLE_BATTERY_LOW] = {}

        for entity in self.entity_ids[CONF_BATTERIES_TO_MONITOR]:
            self.listen_state(
                self.low_battery_detected,
                entity,
                attribute='all',
                constrain_input_boolean=self.enabled_entity_id)

    def low_battery_detected(
            self, entity: Union[str, dict], attribute: str, old: str,
            new: dict, kwargs: dict) -> None:
        """Create OmniFocus todos whenever there's a low battery."""
        name = new['attributes']['friendly_name']

        try:
            value = int(new['state'])
        except ValueError:
            return

        if value < self.properties[CONF_BATTERY_LEVEL_THRESHOLD]:
            if name in self._registered:
                return

            self.log('Low battery detected: {0}'.format(name))

            self._registered.append(name)

            self.handles[HANDLE_BATTERY_LOW][name] = send_notification(
                self,
                'slack',
                '{0} has low batteries ({1})%. Replace them ASAP!'.format(
                    name, value),
                when=self.datetime(),
                interval=self.properties[CONF_NOTIFICATION_INTERVAL])
        else:
            try:
                self._registered.remove(name)
                if name in self.handles[HANDLE_BATTERY_LOW]:
                    cancel = self.handles[HANDLE_BATTERY_LOW].pop(name)
                    cancel()
            except ValueError:
                return


class LeftInState(Base):
    """Define a feature to monitor whether an entity is left in a state."""

    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_ENTITY_IDS: vol.Schema({
            vol.Required(CONF_ENTITY): cv.entity_id,
        }, extra=vol.ALLOW_EXTRA),
        CONF_PROPERTIES: vol.Schema({
            vol.Required(CONF_DURATION): int,
            vol.Required(CONF_STATE): str,
        }, extra=vol.ALLOW_EXTRA),
    })

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self.limit_reached,
            self.entity_ids[CONF_ENTITY],
            new=self.properties[CONF_STATE],
            duration=self.properties[CONF_DURATION],
            constrain_input_boolean=self.enabled_entity_id)

    def limit_reached(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Notify when the threshold is reached."""

        def turn_off():
            """Turn the entity off."""
            self.turn_off(self.entity_ids[CONF_ENTITY])

        self.slack_app_home_assistant.ask(
            'The {0} has been left {1} for {2} minutes. Turn it off?'.format(
                self.get_state(
                    self.entity_ids[CONF_ENTITY], attribute='friendly_name'),
                self.properties[CONF_STATE],
                int(self.properties[CONF_DURATION]) / 60),
            {
                'Yes': {
                    'callback': turn_off,
                    'response_text': 'You got it; turning it off now.'
                },
                'No': {
                    'response_text': 'Keep devouring electricity, little guy.'
                }
            })


class SslExpiration(Base):
    """Define a feature to notify me when the SSL cert is expiring."""

    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_ENTITY_IDS: vol.Schema({
            vol.Required(CONF_SSL_EXPIRY): cv.entity_id,
        }, extra=vol.ALLOW_EXTRA),
        CONF_PROPERTIES: vol.Schema({
            vol.Required(CONF_EXPIRY_THRESHOLD): int,
        }, extra=vol.ALLOW_EXTRA),
    })

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self.ssl_expiration_approaching,
            self.entity_ids[CONF_SSL_EXPIRY],
            constrain_input_boolean=self.enabled_entity_id)

    def ssl_expiration_approaching(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """When SSL is about to expire, make an OmniFocus todo."""
        if int(new) < self.properties[CONF_EXPIRY_THRESHOLD]:
            self.log('SSL certificate about to expire: {0} days'.format(new))

            send_notification(
                self, 'slack/@aaron',
                'SSL expires in less than {0} days'.format(new))


class StartHomeKitOnZwaveReady(Base):
    """Define a feature to start HomeKit when the Z-Wave network is ready."""

    def configure(self) -> None:
        """Configure."""
        self.scan({})

    def network_ready(self) -> bool:
        """Return whether the Z-Wave network is ready."""
        zwave_devices = self.get_state('zwave')
        for attrs in zwave_devices.values():
            try:
                if attrs['state'] != 'ready':
                    return False
            except TypeError:
                return False
        return True

    def scan(self, kwargs: dict) -> None:
        """Start the scanning process."""
        if self.network_ready():
            self.log('Z-Wave network is ready for HomeKit to start')
            self.call_service('homekit/start')
            return

        self.run_in(self.scan, 60)
