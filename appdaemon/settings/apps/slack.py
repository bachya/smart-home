"""Define automations for Slack."""
# pylint: disable=attribute-defined-outside-init,unused-argument

import requests

from automation import Base  # type: ignore
from util import grammatical_list_join  # type: ignore

SECURITY_COMMAND_AWAY = 'away'
SECURITY_COMMAND_HOME = 'home'
SECURITY_COMMAND_GOODNIGHT = 'goodnight'


class Slack(Base):
    """Define a class to interact with a Slack app."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self._last_response_url = None

        self.listen_event(self._slash_command_received, 'SLACK_SLASH_COMMAND')

    def _respond(self, text: str) -> None:
        """Respond to the slash command."""
        requests.post(  # type: ignore
            self._last_response_url,
            headers={'Content-Type': 'application/json'},
            json={'text': text})

    def _slash_command_received(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to 'SLACK_SLASH_COMMAND' events."""
        self._last_response_url = data['response_url']

        try:
            method = getattr(self, data['command'][1:])
            method(data)
        except AttributeError:
            self.error(
                'No implementation of slash command handler: {0}'.format(
                    data['command']))

    def security(self, data: dict) -> None:
        """Interact with the security manager."""
        command = data['text']

        if not command:
            insecure_entities = self.security_system.get_insecure_entities()
            if insecure_entities:
                self._respond(
                    'These entry points are insecure: {0}.'.format(
                        grammatical_list_join(insecure_entities)))
            else:
                self._respond('The house is locked up and secure.')
            return

        if command == SECURITY_COMMAND_AWAY:
            self.call_service('scene/turn_on', entity_id='scene.depart_home')
            self._respond('The house has been fully secured.')
        elif command == SECURITY_COMMAND_GOODNIGHT:
            self.call_service('scene/turn_on', entity_id='scene.good_night')
            self._respond('The house has been secured for the evening.')
        elif command == SECURITY_COMMAND_HOME:
            self.security_system.state = self.security_system.AlarmStates.home
            self._respond('The security system has been set to "Home".')

    def thermostat(self, data: dict) -> None:
        """Interact with the thermostat."""
        command = data['text']

        if not command:
            if self.climate_manager.mode == self.climate_manager.Modes.eco:
                message = 'The thermostat is set to eco mode.'
            else:
                message = 'The thermostat is set to {0} to {1}°.'.format(
                    self.climate_manager.mode,
                    self.climate_manager.indoor_temp)

            self._respond(
                '{0} (current indoor temperature: {1}°)'.format(
                    message, self.climate_manager.average_indoor_temperature))
            return

        self.climate_manager.indoor_temp = int(command)
        self._respond("I've set the thermostat to {0}°.".format(command))
