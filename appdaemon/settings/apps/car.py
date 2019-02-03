"""Define automations for our cars."""
# pylint: disable=attribute-defined-outside-init,unused-argument

from typing import Union

from automation import Automation  # type: ignore

HANDLE_LOW_FUEL = 'low_fuel'


class NotifyLowFuel(Automation):
    """Define a feature to notify of the vehicle's ETA to home."""

    def initialize(self):
        """Initialize."""
        super().initialize()

        self.registered = False

        self.listen_state(
            self.low_fuel_found,
            self.entity_ids['car'],
            attribute='fuel_level',
            constrain_input_boolean=self.enabled_entity_id)

    def low_fuel_found(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str,
            new: str, kwargs: dict) -> None:
        """Send a notification when my car is low on gas."""
        try:
            if int(new) < self.properties['fuel_threshold']:
                if self.registered:
                    return

                self._log.info(
                    'Low fuel detected detected: %s', self.entity_ids['car'])

                self.registered = True
                self.notification_manager.send(
                    "{0} needs gas; fill 'er up!.".format(
                        self.properties['friendly_name']),
                    title='{0} is Low ⛽'.format(
                        self.properties['friendly_name']),
                    target=self.properties['notification_target'])
            else:
                self.registered = False
        except ValueError:
            return
