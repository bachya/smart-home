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
                self._log.info('Setting thermostat to "Away" (extreme temp)')

                self.climate_manager.set_away_mode(
                    self.climate_manager.AwayModes.away)

            # Scenario 2: Away -> Anything (Extreme Temps)
            elif (data['old'] ==
                  self.presence_manager.ProximityStates.away.value
                  and data['new'] !=
                  self.presence_manager.ProximityStates.away.value):
                self._log.info('Setting thermostat to "Home" (extreme temp)')

                self.climate_manager.set_away_mode(
                    self.climate_manager.AwayModes.home)
        else:
            # Scenario 3: Home -> Anything
            if (data['old'] == self.presence_manager.ProximityStates.home.value
                    and data['new'] !=
                    self.presence_manager.ProximityStates.home.value):
                self._log.info('Setting thermostat to "Away"')

                self.climate_manager.set_away_mode(
                    self.climate_manager.AwayModes.away)

            # Scenario 4: Anything -> Nearby
            elif (data['old'] !=
                  self.presence_manager.ProximityStates.nearby.value
                  and data['new'] ==
                  self.presence_manager.ProximityStates.nearby.value):
                self._log.info('Setting thermostat to "Home"')

                self.climate_manager.set_away_mode(
                    self.climate_manager.AwayModes.home)

    def arrived_home(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Last ditch: turn the thermostat to home when someone arrives."""
        if self.climate_manager.away_mode:
            self._log.info(
                'Last ditch: setting thermostat to "Home" (arrived)')

            self.climate_manager.set_away_mode(
                self.climate_manager.AwayModes.home)


class ClimateManager(Base):
    """Define an app to represent climate control."""

    class AwayModes(Enum):
        """Define an enum for thermostat away modes."""

        away = 1
        home = 2

    class Modes(Enum):
        """Define an enum for thermostat modes."""

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

    @property
    def indoor_temp(self) -> int:
        """Return the temperature the thermostat is currently set to."""
        try:
            return int(
                self.get_state(
                    self.entities['thermostat'], attribute='temperature'))
        except TypeError:
            return 0

    @property
    def mode(self) -> Enum:
        """Return the current operating mode."""
        return self.Modes[self.get_state(
            self.entities['thermostat'], attribute='operation_mode')]

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

        self.bump_indoor_temp(int(data['amount']))

        return {
            "status": "ok",
            "message": 'Bumping temperature {0}°'.format(data['amount'])
        }, 200

    def bump_indoor_temp(self, value: int) -> None:
        """Bump the current temperature."""
        self.set_indoor_temp(self.indoor_temp + value)

    def set_away_mode(self, value: "AwayModes") -> None:
        """Set the state of away mode."""
        self.call_service('nest/set_mode', home_mode=value.name)

    def set_indoor_temp(self, value: int) -> None:
        """Set the thermostat temperature."""
        self.call_service(
            'climate/set_temperature',
            entity_id=self.entities['thermostat'],
            temperature=str(value))

    def set_mode(self, value: Enum) -> None:
        """Set the themostat's operating mode."""
        self.call_service(
            'climate/set_operation_mode',
            entity_id=self.entities['thermostat'],
            operation_mode=value.name)


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
