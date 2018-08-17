"""Define automations for our cars."""

# pylint: disable=attribute-defined-outside-init,unused-argument

from datetime import timedelta
from typing import Tuple, Union

from automation import Automation, Feature  # type: ignore


class CarAutomation(Automation):
    """Define an automation for Automatic cars."""


class NotifyEta(Feature):
    """Define a feature to notify of the vehicle's ETA to home."""

    def initialize(self):
        """Initialize."""
        self.hass.register_endpoint(self.get_eta, 'eta')

    def calculate_eta(self, travel_time: str) -> str:
        """Get an arrival time based upon travel time in minutes."""
        eta = self.hass.datetime() + timedelta(minutes=int(travel_time))
        return eta.time().strftime('%I:%M %p')

    def get_eta(self, data: dict) -> Tuple[dict, int]:
        """Define an endpoint to send Aaron's ETA."""
        if self.hass.presence_manager.noone(
                self.hass.presence_manager.HomeStates.home):
            return {
                "status": "ok",
                "message": 'No one home; ignoring'
            }, 200

        try:
            key = data['person']
            name = key.title()
        except KeyError:
            return {
                'status': 'error',
                'message': 'Missing "person" parameter'
            }, 502

        eta = self.calculate_eta(
            self.hass.get_state('sensor.{0}_travel_time'.format(key)))

        self.hass.log("Sending {0}'s ETA: {1}".format(name, eta))

        statement = '{0} is arriving around {1}.'.format(name, eta)
        self.hass.notification_manager.send(
            "Aaron's ETA", statement, target='Britt')
        return {"status": "ok", "message": statement}, 200


class NotifyLowFuel(Feature):
    """Define a feature to notify of the vehicle's ETA to home."""

    def initialize(self):
        """Initialize."""
        self.registered = False
        self.hass.listen_state(
            self.low_fuel_found,
            self.entities['car'],
            attribute='fuel_level',
            constrain_input_boolean=self.enabled_toggle)

    def low_fuel_found(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str,
            new: str, kwargs: dict) -> None:
        """Create an OmniFocus todo whenever my car is low on gas."""
        name = self.hass.get_state(
            self.entities['car'], attribute='friendly_name')

        try:
            if int(new) < self.properties['fuel_threshold']:
                if self.registered:
                    return

                self.hass.log(
                    'Low fuel detected detected: {0}'.format(name))

                self.registered = True
                self.handles[
                    self.hass.
                    friendly_name] = self.hass.notification_manager.repeat(
                        '{0} is Low ⛽'.format(self.hass.friendly_name),
                        "{0} needs gas; fill 'er up!.".format(
                            self.hass.friendly_name),
                        self.properties['notification_interval'],
                        target='home')
            else:
                self.registered = False
                if self.hass.friendly_name in self.handles:
                    self.handles.pop(self.hass.friendly_name)()
        except ValueError:
            return
