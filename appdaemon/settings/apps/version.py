"""Define automations for tracking software versions."""
from time import sleep
from typing import Union

import requests
import voluptuous as vol
from packaging import version  # type: ignore

from core import APP_SCHEMA, Base
from const import (
    CONF_ENTITY_IDS, CONF_FRIENDLY_NAME, CONF_PROPERTIES, CONF_UPDATE_INTERVAL)
from helpers import config_validation as cv

CONF_APP_NAME = 'app_name'
CONF_AVAILABLE = 'available'
CONF_CREATED_ENTITY_ID = 'created_entity_id'
CONF_ENDPOINT_ID = 'endpoint_id'
CONF_FRIENDLY_NAME = 'friendly_name'
CONF_ICON = 'icon'
CONF_IMAGE_NAME = 'image_name'
CONF_INSTALLED = 'installed'
CONF_TASMOTA_HOSTS = 'tasmota_hosts'

DEFAULT_DYNAMIC_RETRIES = 3


class NewVersionNotification(Base):
    """Define a feature to detect new versions of key apps."""

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self.version_change_detected,
            self.entity_ids[CONF_AVAILABLE],
            constrain_input_boolean=self.enabled_entity_id)

    def version_change_detected(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Notify me when there's a new app version."""
        new_version = version.parse(
            self.get_state(self.entity_ids[CONF_AVAILABLE]))
        installed_version = version.parse(
            self.get_state(self.entity_ids[CONF_INSTALLED]))

        if new_version > installed_version:
            self.log(
                'New {0} version detected: {1}'.format(
                    self.properties[CONF_APP_NAME], new))

            self.notification_manager.send(
                'New {0} Version: {1}'.format(
                    self.properties[CONF_APP_NAME], new),
                title='New Software 💿',
                target=['Aaron', 'slack'])


class DynamicSensor(NewVersionNotification):
    """Define a feature to generate a dynamic version sensor."""

    def configure(self) -> None:
        """Configure."""
        self.run_every(
            self.update_sensor, self.datetime(),
            self.properties[CONF_UPDATE_INTERVAL])

    @property
    def sensor_value(self) -> Union[None, str]:
        """Raise if not implemented."""
        raise NotImplementedError()

    def update_sensor(self, kwargs: dict) -> None:
        """Update sensor value."""
        self.set_state(
            self.properties[CONF_CREATED_ENTITY_ID],
            state=str(self.sensor_value),
            attributes={
                'friendly_name': self.properties[CONF_FRIENDLY_NAME],
                'icon': self.properties[CONF_ICON],
            })


class NewPortainerVersionNotification(DynamicSensor):
    """Define a feature to detect new versions Portainer-defined images."""

    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_ENTITY_IDS: vol.Schema({
            vol.Required(CONF_AVAILABLE): cv.entity_id,
            vol.Required(CONF_INSTALLED): cv.entity_id,
        }, extra=vol.ALLOW_EXTRA),
        CONF_PROPERTIES: vol.Schema({
            vol.Required(CONF_APP_NAME): str,
            vol.Required(CONF_CREATED_ENTITY_ID): cv.entity_id,
            vol.Required(CONF_ENDPOINT_ID): int,
            vol.Required(CONF_FRIENDLY_NAME): str,
            vol.Required(CONF_ICON): str,
            vol.Required(CONF_IMAGE_NAME): str,
            vol.Required(CONF_UPDATE_INTERVAL): int,
        }, extra=vol.ALLOW_EXTRA),
    })

    API_URL = 'http://portainer:9000/api'

    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_ENTITY_IDS: vol.Schema({
            vol.Required(CONF_AVAILABLE): cv.entity_id,
            vol.Required(CONF_INSTALLED): cv.entity_id,
        }, extra=vol.ALLOW_EXTRA),
        CONF_PROPERTIES: vol.Schema({
            vol.Required(CONF_APP_NAME): str,
        }, extra=vol.ALLOW_EXTRA),
    })


    @property
    def sensor_value(self) -> Union[None, str]:
        """Get the version from Portainer."""
        auth_resp = requests.post(
            '{0}/auth'.format(self.API_URL),
            json={
                'Username': self.config['portainer_username'],
                'Password': self.config['portainer_password']
            }).json()
        token = auth_resp['jwt']

        images_resp = requests.get(
            '{0}/endpoints/{1}/docker/images/json'.format(
                self.API_URL, self.properties[CONF_ENDPOINT_ID]),
            headers={
                'Authorization': 'Bearer {0}'.format(token)
            }).json()

        try:
            tagged_image = next((
                i for image in images_resp for i in image['RepoTags']
                if self.properties[CONF_IMAGE_NAME] in i))
        except StopIteration:
            self.error(
                'No match for image: {0}'.format(
                    self.properties[CONF_IMAGE_NAME]))

        return tagged_image.split(':')[1].replace('v', '').split('-')[0]


class NewTasmotaVersionNotification(DynamicSensor):
    """Define a feature to detect new versions of Tasmota."""

    APP_SCHEMA = APP_SCHEMA.extend({
        CONF_ENTITY_IDS: vol.Schema({
            vol.Required(CONF_AVAILABLE): cv.entity_id,
            vol.Required(CONF_INSTALLED): cv.entity_id,
        }, extra=vol.ALLOW_EXTRA),
        CONF_PROPERTIES: vol.Schema({
            vol.Required(CONF_APP_NAME): str,
            vol.Required(CONF_CREATED_ENTITY_ID): cv.entity_id,
            vol.Required(CONF_FRIENDLY_NAME): str,
            vol.Required(CONF_ICON): str,
            vol.Required(CONF_TASMOTA_HOSTS): cv.ensure_list,
            vol.Required(CONF_UPDATE_INTERVAL): int,
        }, extra=vol.ALLOW_EXTRA),
    })

    @property
    def sensor_value(self) -> Union[None, str]:
        """Get the lowest Tasmota version from all Sonoffs."""
        lowest_version = None
        status_uri = 'cm?cmnd=Status%202'
        tasmota_version = None

        for host in self.properties[CONF_TASMOTA_HOSTS]:
            for _ in range(DEFAULT_DYNAMIC_RETRIES - 1):
                try:
                    json = requests.get(
                        'http://{0}/{1}'.format(host, status_uri)).json()
                    tasmota_version = json['StatusFWR']['Version']
                except requests.exceptions.ConnectionError:
                    sleep(10)
                else:
                    break

            try:
                if lowest_version > tasmota_version:  # type: ignore
                    lowest_version = tasmota_version
            except TypeError:
                lowest_version = tasmota_version

        if not lowest_version:
            self.error("Couldn't reach any Tasmota host")
            return None

        return lowest_version
