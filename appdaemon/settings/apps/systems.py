"""Define automations for various home systems."""
# pylint: disable=attribute-defined-outside-init,unused-argument

from typing import Union

from automation import Automation  # type: ignore

HANDLE_BATTERY_LOW = 'battery_low'


class LowBatteries(Automation):
    """Define a feature to notify us of low batteries."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self._registered = []  # type: ignore
        self.handles[HANDLE_BATTERY_LOW] = {}

        for entity in self.entities['batteries_to_monitor']:
            self.listen_state(
                self.low_battery_detected,
                entity,
                attribute='all',
                constrain_input_boolean=self.enabled_entity_id)

    def low_battery_detected(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str,
            new: dict, kwargs: dict) -> None:
        """Create OmniFocus todos whenever there's a low battery."""
        name = new['attributes']['friendly_name']

        try:
            value = int(new['state'])
        except ValueError:
            return

        if value < self.properties['battery_level_threshold']:
            if name in self._registered:
                return

            self.log('Low battery detected: {0}'.format(name))

            self._registered.append(name)

            self.handles[HANDLE_BATTERY_LOW][
                name] = self.notification_manager.repeat(
                    '{0} has low batteries ({1})%. Replace them ASAP!'.format(
                        name, value),
                    self.properties['notification_interval'],
                    target='slack')
        else:
            try:
                self._registered.remove(name)
                if name in self.handles[HANDLE_BATTERY_LOW]:
                    self.handles[HANDLE_BATTERY_LOW].pop(name)()
            except ValueError:
                return


class LeftInState(Automation):
    """Define a feature to monitor whether an entity is left in a state."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_state(
            self.limit_reached,
            self.entities['entity'],
            new=self.properties['state'],
            duration=self.properties['seconds'],
            constrain_input_boolean=self.enabled_entity_id)

    def limit_reached(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Notify when the threshold is reached."""
        self.notification_manager.send(
            'The {0} has been left {1} for {2} minutes. Use `/toggle {3} off` '
            'to turn it off'.format(
                self.get_state(
                    self.entities['entity'],
                    attribute='friendly_name'), self.properties['state'],
                int(self.properties['seconds']) / 60,
                self.entities['entity'].split('.')[1]),
            target='slack')


class SslExpiration(Automation):
    """Define a feature to notify me when the SSL cert is expiring."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_state(
            self.ssl_expiration_approaching,
            self.entities['ssl_expiry'],
            constrain_input_boolean=self.enabled_entity_id)

    def ssl_expiration_approaching(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """When SSL is about to expire, make an OmniFocus todo."""
        if int(new) < self.properties['expiry_threshold']:
            self.log('SSL certificate about to expire: {0} days'.format(new))

            self.notification_manager.create_omnifocus_task(
                'SSL expires in less than {0} days'.format(new))
