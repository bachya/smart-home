"""Define automations for various home systems."""

# pylint: disable=attribute-defined-outside-init,unused-argument

from typing import Union

from automation import Automation, Feature  # type: ignore


class SystemsAutomation(Automation):
    """Define a class to represent automations for systems."""


class LowBatteries(Feature):
    """Define a feature to notify us of low batteries."""

    def initialize(self) -> None:
        """Initialize."""
        self._registered = []  # type: ignore

        for entity in self.properties['batteries_to_monitor']:
            self.hass.listen_state(
                self.low_battery_detected,
                entity,
                attribute='all',
                constrain_input_boolean=self.constraint)

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

            self.hass.log('Low battery detected: {0}'.format(name))

            self._registered.append(name)

            self.handles[name] = self.hass.notification_manager.repeat(
                'Low Batteries 🔋',
                '{0} is at {1}%. Replace the batteries ASAP!'.format(
                    name, value),
                60 * 15,
                target='home')
        else:
            try:
                self._registered.remove(name)
                if name in self.handles:
                    self.handles.pop(name)()
            except ValueError:
                return


class LeftInState(Feature):
    """Define a feature to monitor whether an entity is left in a state."""

    def initialize(self) -> None:
        """Initialize."""
        self.hass.listen_state(
            self.limit_reached,
            self.entities['entity'],
            new=self.properties['state'],
            duration=self.properties['seconds'],
            constrain_input_boolean=self.constraint)

    def limit_reached(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Notify when the threshold is reached."""
        self.hass.notification_manager.send(
            'Entity Checkup',
            '{0} has been left {1} for {2} minutes.'.format(
                self.hass.get_state(
                    self.entities['entity'], attribute='friendly_name'),
                self.properties['state'],
                int(self.properties['seconds']) / 60),
            target='Aaron')


class NightlyTasks(Feature):
    """Define a feature to run various nightly tasks."""

    def initialize(self) -> None:
        """Initialize."""
        self.hass.run_daily(
            self.night_has_arrived,
            self.hass.parse_time(self.properties['tasks_schedule_time']),
            constrain_input_boolean=self.constraint)

    def night_has_arrived(self, kwargs: dict) -> None:
        """Perform nightly tasks."""
        self.hass.log('Performing nightly tasks')

        self.hass.turn_on(self.entities['auto_arm'])


class SslExpiration(Feature):
    """Define a feature to notify me when the SSL cert is expiring."""

    def initialize(self) -> None:
        """Initialize."""
        self.hass.listen_state(
            self.ssl_expiration_approaching,
            self.entities['ssl_expiry'],
            constrain_input_boolean=self.constraint)

    def ssl_expiration_approaching(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """When SSL is about to expire, make an OmniFocus todo."""
        if int(new) < self.properties['expiry_threshold']:
            self.hass.log(
                'SSL certificate about to expire: {0} days'.format(new))

            self.hass.notification_manager.create_omnifocus_task(
                'SSL expires in less than {0} days'.format(new))
