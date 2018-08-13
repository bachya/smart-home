"""Define automations for climate control."""

# pylint: disable=attribute-defined-outside-init,unused-argument

from typing import Tuple, Union

from app import App  # type: ignore
from automation import Automation, Feature  # type: ignore


class ClimateManager(App):
    """Define an app to represent climate control."""

    @property
    def average_indoor_humidity(self) -> float:
        """Return the average indoor humidity based on a list of sensors."""
        return float(self.get_state(self.entities['average_indoor_humidity']))

    @property
    def average_indoor_temperature(self) -> float:
        """Return the average indoor temperature based on a list of sensors."""
        return float(
            self.get_state(self.entities['average_indoor_temperature']))

    @property
    def away_mode(self) -> bool:
        """Return the state of away mode."""
        return self.get_state(
            self.entities['thermostat'], attribute='away_mode') == 'on'

    @away_mode.setter
    def away_mode(self, value: Union[int, bool, str]) -> None:
        """Set the state of away mode."""
        self.call_service(
            'nest/set_mode',
            home_mode='away' if value in (1, True, 'on') else 'home')

    @property
    def indoor_temp(self) -> int:
        """Return the temperature the thermostat is currently set to."""
        return int(
            self.get_state(
                self.entities['thermostat'], attribute='current_temperature'))

    @indoor_temp.setter
    def indoor_temp(self, value: int) -> None:
        """Set the thermostat temperature."""
        self.call_service(
            'climate/set_temperature',
            entity_id=self.entities['thermostat'],
            temperature=str(value))

    @property
    def outside_temp(self) -> float:
        """Define a property to get the current outdoor temperature."""
        return float(self.get_state(self.entities['outside_temp']))

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.register_endpoint(self._climate_bump_endpoint, 'climate_bump')

    def _climate_bump_endpoint(self, data: dict) -> Tuple[dict, int]:
        """Define an endpoint to quickly bump the climate."""
        if not data.get('amount'):
            return {
                'status': 'error',
                'message': 'Missing "amount" parameter'
            }, 502

        # Anticipating that we'll get values like "5" and "-3" from the API
        # call:
        target_temp = self.indoor_temp + int(data['amount'])
        self.indoor_temp = target_temp
        return {
            "status":
                "ok",
            "message":
                'Bumping temperature {0}° (to {1}°)'.format(
                    data['amount'], target_temp)
        }, 200


class ClimateAutomation(Automation):
    """Define an automation to manage climate."""


class AdjustOnProximity(Feature):
    """Define a feature to adjust climate based on proximity to home."""

    def initialize(self) -> None:
        """Initialize."""
        self.hass.listen_event(
            self.arrived_home,
            'PRESENCE_CHANGE',
            new=self.hass.presence_manager.HomeStates.just_arrived.value,
            first=True,
            constrain_input_boolean=self.constraint)
        self.hass.listen_event(
            self.proximity_changed,
            'PROXIMITY_CHANGE',
            constrain_input_boolean=self.constraint)

    def proximity_changed(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to "PROXIMITY_CHANGE" events."""
        if (self.hass.climate_manager.outside_temp <
                self.properties['outside_threshold_low']
                or self.hass.climate_manager.outside_temp >
                self.properties['outside_threshold_high']):

            # Scenario 1: Anything -> Away (Extreme Temps)
            if (data['old'] !=
                    self.hass.presence_manager.ProximityStates.away.value
                    and data['new'] ==
                    self.hass.presence_manager.ProximityStates.away.value):
                self.hass.log(
                    'Setting thermostat to "Away" (extreme temp)')
                self.hass.climate_manager.away_mode = True

            # Scenario 2: Away -> Anything (Extreme Temps)
            elif (data['old'] ==
                  self.hass.presence_manager.ProximityStates.away.value
                  and data['new'] !=
                  self.hass.presence_manager.ProximityStates.away.value):
                self.hass.log(
                    'Setting thermostat to "Home" (extreme temp)')
                self.hass.climate_manager.away_mode = False
        else:
            # Scenario 3: Home -> Anything
            if (data['old'] ==
                    self.hass.presence_manager.ProximityStates.home.value
                    and data['new'] !=
                    self.hass.presence_manager.ProximityStates.home.value):
                self.hass.log('Setting thermostat to "Away"')
                self.hass.climate_manager.away_mode = True

            # Scenario 4: Anything -> Nearby
            elif (data['old'] !=
                  self.hass.presence_manager.ProximityStates.nearby.value
                  and data['new'] ==
                  self.hass.presence_manager.ProximityStates.nearby.value):
                self.hass.log('Setting thermostat to "Home"')
                self.hass.climate_manager.away_mode = False

    def arrived_home(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Last ditch: turn the thermostat to home when someone arrives."""
        if self.hass.climate_manager.away_mode:
            self.hass.log(
                'Last ditch: setting thermostat to "Home" (arrived)')
            self.hass.climate_manager.away_mode = False


class NotifyBadAqi(Feature):
    """Define a feature to notify us of bad air quality."""

    @property
    def current_aqi(self) -> int:
        """Define a property to get the current AQI."""
        return int(self.hass.get_state(self.entities['aqi']))

    def initialize(self) -> None:
        """Initialize."""
        self.notification_sent = False

        self.hass.listen_state(
            self.bad_aqi_detected,
            self.entities['hvac_state'],
            new='cooling',
            constrain_input_boolean=self.constraint)

    def bad_aqi_detected(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str,
            new: str, kwargs: dict) -> None:
        """Send select notifications when cooling and poor AQI."""
        if (not self.notification_sent
                and self.current_aqi > self.properties['aqi_threshold']):
            self.hass.log('Poor AQI; notifying anyone at home')

            self.hass.notification_manager.send(
                'Poor AQI',
                'AQI is at {0}; consider closing the humidifier vent.'.
                format(self.current_aqi),
                target='home')
            self.notification_sent = True
        elif (self.notification_sent
              and self.current_aqi <= self.properties['aqi_threshold']):
            self.hass.notification_manager.send(
                'Better AQI',
                'AQI is at {0}; open the humidifer vent again.'.format(
                    self.current_aqi),
                target='home')
            self.notification_sent = True
