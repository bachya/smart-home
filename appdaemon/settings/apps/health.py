"""Define automations for health."""
# pylint: disable=attribute-defined-outside-init,unused-argument
from typing import Union

from automation import Automation  # type: ignore


class NotifyBadAqi(Automation):
    """Define a feature to notify us of bad air quality."""

    @property
    def current_aqi(self) -> int:
        """Define a property to get the current AQI."""
        return int(self.get_state(self.entity_ids['aqi']))

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.notification_sent = False

        self.listen_state(
            self.bad_aqi_detected,
            self.entity_ids['hvac_state'],
            new='cooling',
            constrain_input_boolean=self.enabled_entity_id)

    def bad_aqi_detected(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Send select notifications when cooling and poor AQI."""
        if (not self.notification_sent
                and self.current_aqi > self.properties['aqi_threshold']):
            self._log.info('Poor AQI; notifying anyone at home')

            self.notification_manager.send(
                'AQI is at {0}; consider closing the humidifier vent.'.format(
                    self.current_aqi),
                title='Poor AQI 😤',
                target='home')
            self.notification_sent = True
        elif (self.notification_sent
              and self.current_aqi <= self.properties['aqi_threshold']):
            self.notification_manager.send(
                'AQI is at {0}; open the humidifer vent again.'.format(
                    self.current_aqi),
                title='Better AQI 😅',
                target='home')
            self.notification_sent = True


class UpdateUvWhenSunny(Automation):
    """Define a feature to update OpenUV data when the sun is up."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.run_every(
            self.update_data,
            self.datetime(),
            self.properties['update_interval'],
            constrain_sun='up')

    def update_data(self, kwargs: dict) -> None:
        """Update sensor value."""
        self._log.debug('Updating OpenUV data')

        self.call_service('openuv/update_data')
