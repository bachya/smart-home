"""Define automations for health."""
from typing import Union

from core import Base
from const import BLACKOUT_START


class AaronAccountability(Base):
    """Define features to keep me accountable on my phone."""

    def configure(self) -> None:
        """Configure."""
        self.run_daily(
            self.send_notification_when_blackout_start,
            self.parse_time(BLACKOUT_START))

        self.listen_state(
            self.send_notification_on_disconnect,
            self.entity_ids['aaron_router_tracker'],
            new='not_home',
            constrain_in_blackout=True,
            constrain_anyone='home')

    @property
    def router_tracker_state(self) -> str:
        """Return the state of Aaron's Unifi tracker."""
        return self.get_state(self.entity_ids['aaron_router_tracker'])

    def _send_notification(self) -> None:
        """Send notification to my love."""
        self.notification_manager.send(
            "His phone shouldn't be off wifi during the night.",
            title='Check on Aaron',
            target='Britt')

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

    @property
    def current_aqi(self) -> int:
        """Define a property to get the current AQI."""
        return int(self.get_state(self.entity_ids['aqi']))

    def configure(self) -> None:
        """Configure."""
        self.notification_sent = False

        self.listen_state(
            self.bad_aqi_detected,
            self.entity_ids['hvac_state'],
            new='cooling',
            constrain_input_boolean=self.enabled_entity_id)

    def bad_aqi_detected(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Send select notifications when cooling and poor AQI."""
        if (not self.notification_sent
                and self.current_aqi > self.properties['aqi_threshold']):
            self.log('Poor AQI; notifying anyone at home')

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


class UpdateUvWhenSunny(Base):
    """Define a feature to update OpenUV data when the sun is up."""

    def configure(self) -> None:
        """Configure."""
        self.run_every(
            self.update_data,
            self.datetime(),
            self.properties['update_interval'],
            constrain_sun='up')

    def update_data(self, kwargs: dict) -> None:
        """Update sensor value."""
        from requests.exceptions import HTTPError

        try:
            self.call_service('openuv/update_data')
        except HTTPError as err:
            self.error('Error while updating OpenUV: {0}'.format(err))
