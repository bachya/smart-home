"""Define automations for climate control."""
# pylint: disable=attribute-defined-outside-init,unused-argument

from enum import Enum
from typing import Tuple, Union

from automation import Automation, Base  # type: ignore


class AdjustOnProximity(Automation):
    """Define a feature to adjust climate based on proximity to home."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_event(
            self.arrived_home,
            'PRESENCE_CHANGE',
            new=self.presence_manager.HomeStates.just_arrived.value,
            first=True,
            constrain_input_boolean=self.enabled_entity_id)
        self.listen_event(
            self.proximity_changed,
            'PROXIMITY_CHANGE',
            constrain_input_boolean=self.enabled_entity_id)

    def proximity_changed(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to "PROXIMITY_CHANGE" events."""
        if (self.climate_manager.outside_temp <
                self.properties['outside_threshold_low']
                or self.climate_manager.outside_temp >
                self.properties['outside_threshold_high']):

            # Scenario 1: Anything -> Away (Extreme Temps)
            if (data['old'] != self.presence_manager.ProximityStates.away.value
                    and data['new'] ==
                    self.presence_manager.ProximityStates.away.value):
                self.log('Setting thermostat to "Away" (extreme temp)')
                self.climate_manager.away_mode = True

            # Scenario 2: Away -> Anything (Extreme Temps)
            elif (data['old'] ==
                  self.presence_manager.ProximityStates.away.value
                  and data['new'] !=
                  self.presence_manager.ProximityStates.away.value):
                self.log('Setting thermostat to "Home" (extreme temp)')
                self.climate_manager.away_mode = False
        else:
            # Scenario 3: Home -> Anything
            if (data['old'] == self.presence_manager.ProximityStates.home.value
                    and data['new'] !=
                    self.presence_manager.ProximityStates.home.value):
                self.log('Setting thermostat to "Away"')
                self.climate_manager.away_mode = True

            # Scenario 4: Anything -> Nearby
            elif (data['old'] !=
                  self.presence_manager.ProximityStates.nearby.value
                  and data['new'] ==
                  self.presence_manager.ProximityStates.nearby.value):
                self.log('Setting thermostat to "Home"')
                self.climate_manager.away_mode = False

    def arrived_home(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Last ditch: turn the thermostat to home when someone arrives."""
        if self.climate_manager.away_mode:
            self.log('Last ditch: setting thermostat to "Home" (arrived)')
            self.climate_manager.away_mode = False


class ClimateManager(Base):
    """Define an app to represent climate control."""

    class Modes(Enum):
        """Define an enum for alarm states."""

        auto = 1
        cool = 2
        eco = 3
        heat = 4
        off = 5

    @property
    def average_indoor_humidity(self) -> float:
        """Return the average indoor humidity based on a list of sensors."""
        return float(self.get_state(self.entities['average_humidity_sensor']))

    @property
    def average_indoor_temperature(self) -> float:
        """Return the average indoor temperature based on a list of sensors."""
        return float(
            self.get_state(self.entities['average_temperature_sensor']))

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
                self.entities['thermostat'], attribute='temperature'))

    @indoor_temp.setter
    def indoor_temp(self, value: int) -> None:
        """Set the thermostat temperature."""
        self.call_service(
            'climate/set_temperature',
            entity_id=self.entities['thermostat'],
            temperature=str(value))

    @property
    def mode(self) -> Enum:
        """Return the current operating mode."""
        return self.Modes[self.get_state(
            self.entities['thermostat'], attribute='operation_mode')]

    @mode.setter
    def mode(self, value: Enum) -> None:
        """Set the themostat's operating mode."""
        self.call_service(
            'climate/set_operation_mode',
            entity_id=self.entities['thermostat'],
            operation_mode=value.name)

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


class NotifyBadAqi(Automation):
    """Define a feature to notify us of bad air quality."""

    @property
    def current_aqi(self) -> int:
        """Define a property to get the current AQI."""
        return int(self.get_state(self.entities['aqi']))

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.notification_sent = False

        self.listen_state(
            self.bad_aqi_detected,
            self.entities['hvac_state'],
            new='cooling',
            constrain_input_boolean=self.enabled_entity_id)

    def bad_aqi_detected(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str,
            new: str, kwargs: dict) -> None:
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
