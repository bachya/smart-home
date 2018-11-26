"""Define automations for plants."""
# pylint: disable=attribute-defined-outside-init,unused-argument

from typing import Union

from automation import Automation  # type: ignore

HANDLE_LOW_MOISTURE = 'low_moisture'


class LowMoisture(Automation):
    """Define a feature to notify us of low moisture."""

    @property
    def current_moisture(self) -> int:
        """Define a property to get the current moisture."""
        return int(self.get_state(self.entities['current_moisture']))

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self._low_moisture = False

        self.listen_state(
            self.low_moisture_detected,
            self.entities['current_moisture'],
            constrain_input_boolean=self.enabled_entity_id)

    def low_moisture_detected(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Notify when the plant's moisture is low."""
        if (not (self._low_moisture)
                and int(new) < int(self.properties['moisture_threshold'])):
            self._log.info(
                'Notifying people at home that plant is low on moisture')

            self._low_moisture = True
            self.handles[
                HANDLE_LOW_MOISTURE] = self.notification_manager.repeat(
                    '{0} is at {1}% moisture and needs water.'.format(
                        self.properties['friendly_name'],
                        self.current_moisture),
                    self.properties['notification_interval'],
                    title='{0} is Dry 💧'.format(
                        self.properties['friendly_name']),
                    target='home')
        else:
            self._low_moisture = False
            if HANDLE_LOW_MOISTURE in self.handles:
                self.handles.pop(HANDLE_LOW_MOISTURE)()
