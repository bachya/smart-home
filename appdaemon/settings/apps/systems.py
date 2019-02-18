"""Define automations for various home systems."""
from typing import Union

from core import Base

HANDLE_BATTERY_LOW = 'battery_low'


class LowBatteries(Base):
    """Define a feature to notify us of low batteries."""

    def configure(self) -> None:
        """Configure."""
        self._registered = []  # type: ignore
        self.handles[HANDLE_BATTERY_LOW] = {}

        for entity in self.entity_ids['batteries_to_monitor']:
            self.listen_state(
                self.low_battery_detected,
                entity,
                attribute='all',
                constrain_input_boolean=self.enabled_entity_id)

    def low_battery_detected(
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

            self._log.info('Low battery detected: %s', name)

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


class LeftInState(Base):
    """Define a feature to monitor whether an entity is left in a state."""

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self.limit_reached,
            self.entity_ids['entity'],
            new=self.properties['state'],
            duration=self.properties['seconds'],
            constrain_input_boolean=self.enabled_entity_id)

    def limit_reached(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Notify when the threshold is reached."""

        def turn_off():
            """Turn the entity off."""
            self.turn_off(self.entity_ids['entity'])

        self.slack_app_home_assistant.ask(
            'The {0} has been left {1} for {2} minutes. Turn it off?'.format(
                self.get_state(
                    self.entity_ids['entity'], attribute='friendly_name'),
                self.properties['state'],
                int(self.properties['seconds']) / 60),
            {
                'Yes': {
                    'callback': turn_off,
                    'response_text': 'You got it; turning it off now.'
                },
                'No': {
                    'response_text': 'Keep devouring electricity, little guy.'
                }
            })


class SslExpiration(Base):
    """Define a feature to notify me when the SSL cert is expiring."""

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self.ssl_expiration_approaching,
            self.entity_ids['ssl_expiry'],
            constrain_input_boolean=self.enabled_entity_id)

    def ssl_expiration_approaching(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """When SSL is about to expire, make an OmniFocus todo."""
        if int(new) < self.properties['expiry_threshold']:
            self._log.info('SSL certificate about to expire: %s days', new)

            self.notification_manager.create_omnifocus_task(
                'SSL expires in less than {0} days'.format(new))
