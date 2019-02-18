"""Define automations for our cars."""
from typing import Union

from core import Base

HANDLE_LOW_FUEL = 'low_fuel'


class NotifyLowFuel(Base):
    """Define a feature to notify of the vehicle's ETA to home."""

    def configure(self):
        """Configure."""
        self.registered = False

        self.listen_state(
            self.low_fuel_found,
            self.entity_ids['car'],
            attribute='fuel_level',
            constrain_input_boolean=self.enabled_entity_id)

    def low_fuel_found(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Send a notification when my car is low on gas."""
        try:
            if int(new) < self.properties['fuel_threshold']:
                if self.registered:
                    return

                self.log(
                    'Low fuel detected detected: {0}'.format(
                        self.entity_ids['car']))

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
