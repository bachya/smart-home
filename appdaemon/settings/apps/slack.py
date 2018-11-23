"""Define automations for Slack."""
# pylint: disable=attribute-defined-outside-init,unused-argument

import requests

from automation import Base  # type: ignore
from util import grammatical_list_join, relative_search_dict  # type: ignore

SECURITY_COMMAND_AWAY = 'away'
SECURITY_COMMAND_HOME = 'home'
SECURITY_COMMAND_GOODNIGHT = 'goodnight'

TOGGLE_MAP = {'Media Center': 'switch.media_center', 'PS4': 'switch.ps4'}


class Slack(Base):
    """Define a class to interact with a Slack app."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self._last_response_url = None

        self.listen_event(self._slash_command_received, 'SLACK_SLASH_COMMAND')

    def _respond(self, text: str, attachments: list = None) -> None:
        """Respond to the slash command."""
        payload = {'text': text}
        if attachments:
            payload['attachments'] = attachments  # type: ignore

        requests.post(  # type: ignore
            self._last_response_url,
            headers={'Content-Type': 'application/json'},
            json=payload)

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
            insecure_entities = self.security_manager.get_insecure_entities()
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
            self.security_manager.state = self.security_manager.States.home
            self._respond('The security system has been set to "Home".')

    def thermostat(self, data: dict) -> None:
        """Interact with the thermostat."""
        command = data['text']

        if not command:
            if self.climate_manager.mode == self.climate_manager.Modes.eco:
                message = 'The thermostat is set to eco mode.'
            else:
                message = 'The thermostat is set to {0} to {1}°.'.format(
                    self.climate_manager.mode.name,
                    self.climate_manager.indoor_temp)

            self._respond(
                '{0} (current indoor temperature: {1}°)'.format(
                    message, self.climate_manager.average_indoor_temperature))
            return

        self.climate_manager.indoor_temp = int(command)
        self._respond("I've set the thermostat to {0}°.".format(command))

    def toggle(self, data: dict) -> None:
        """Toggle an entity."""
        command = data['text']
        target, state = command.split(' ')

        if state not in ('off', 'on'):
            self._respond("\"{0}\" isn't a valid state.".format(state))
            return

        try:
            _, entity = relative_search_dict(TOGGLE_MAP, target)
        except ValueError:
            self._respond("I'm sorry, I don't know \"{0}\".".format(target))
            return

        method = getattr(self, 'turn_{0}'.format(state))
        method(entity)
        self._respond("I've turned \"{0}\" {1}.".format(entity, state))
