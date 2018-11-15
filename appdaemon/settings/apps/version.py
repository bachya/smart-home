"""Define automations for tracking software versions."""
# pylint: disable=attribute-defined-outside-init,import-error,unused-argument

from time import sleep
from typing import Union

import requests
from packaging import version  # type: ignore

from automation import Automation  # type: ignore

DEFAULT_DYNAMIC_RETRIES = 3


class NewVersionNotification(Automation):
    """Define a feature to detect new versions of key apps."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_state(
            self.version_change_detected,
            self.entities['available'],
            constrain_input_boolean=self.enabled_entity_id)

    def version_change_detected(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Notify me when there's a new app version."""
        new_version = version.parse(self.get_state(self.entities['available']))
        installed_version = version.parse(
            self.get_state(self.entities['installed']))

        if new_version > installed_version:
            self.log('New {0} version detected: {1}'.format(
                self.properties['app_name'], new))

            self.notification_manager.send(
                'New {0} Version: {1}'.format(self.properties['app_name'],
                                              new),
                title='New Software 💿',
                target=['Aaron', 'slack'])


class DynamicSensor(NewVersionNotification):
    """Define a feature to generate a dynamic version sensor."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.run_every(self.update_sensor, self.datetime(),
                       self.properties['update_interval'])

    def update_sensor(self, kwargs: dict) -> None:
        """Update sensor value."""
        self.set_state(
            self.properties['created_entity_id'],
            state=str(self.sensor_value),
            attributes={
                'friendly_name': self.properties['friendly_name'],
                'icon': self.properties['icon'],
            })


class NewPortainerVersionNotification(DynamicSensor):
    """Define a feature to detect new versions Portainer-defined images."""

    API_URL = 'http://portainer:9000/api'

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
                self.API_URL, self.properties['endpoint_id']),
            headers={
                'Authorization': 'Bearer {0}'.format(token)
            }).json()

        try:
            tagged_image = next((i for image in images_resp
                                 for i in image['RepoTags']
                                 if self.properties['image_name'] in i))
        except StopIteration:
            self.error('No match for image: {0}'.format(
                self.properties['image_name']))

        return tagged_image.split(':')[1]


class NewTasmotaVersionNotification(DynamicSensor):
    """Define a feature to detect new versions of Tasmota."""

    @property
    def sensor_value(self) -> Union[None, str]:
        """Get the lowest Tasmota version from all Sonoffs."""
        lowest_version = None
        status_uri = 'cm?cmnd=Status%202'
        tasmota_version = None

        for host in self.properties['tasmota_hosts']:
            for _ in range(DEFAULT_DYNAMIC_RETRIES - 1):
                try:
                    json = requests.get('http://{0}/{1}'.format(
                        host, status_uri)).json()
                    tasmota_version = json['StatusFWR']['Version']
                except requests.exceptions.ConnectionError:
                    sleep(10)
                else:
                    break
            else:
                self.error('Unable to connect to host: {0}'.format(host))

            try:
                if lowest_version > tasmota_version:  # type: ignore
                    lowest_version = tasmota_version
            except TypeError:
                lowest_version = tasmota_version

        return lowest_version
