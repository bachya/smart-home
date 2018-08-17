"""Define automations for plants."""

# pylint: disable=attribute-defined-outside-init,unused-argument

from typing import Union

from automation import Automation, Feature  # type: ignore


class PlantAutomation(Automation):
    """Define an automation for plants."""


class LowMoisture(Feature):
    """Define a feature to notify us of low moisture."""

    @property
    def current_moisture(self) -> int:
        """Define a property to get the current moisture."""
        return int(self.hass.get_state(self.entities['current_moisture']))

    def initialize(self) -> None:
        """Initialize."""
        self._low_moisture = False

        self.hass.listen_state(
            self.low_moisture_detected,
            self.entities['current_moisture'],
            constrain_input_boolean=self.enabled_toggle)

    def low_moisture_detected(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Notify when the plant's moisture is low."""
        if (not (self._low_moisture)
                and int(new) < int(self.properties['moisture_threshold'])):
            self.hass.log(
                'Notifying people at home that plant is low on moisture')

            self._low_moisture = True
            self.handles[
                self.hass.
                friendly_name] = self.hass.notification_manager.repeat(
                    '{0} is Dry 💧'.format(self.hass.friendly_name),
                    '{0} is at {1}% moisture and needs water.'.format(
                        self.hass.friendly_name, self.current_moisture),
                    60 * 60,
                    target='home')
        else:
            self._low_moisture = False
            if self.hass.friendly_name in self.handles:
                self.handles.pop(self.hass.friendly_name)()
