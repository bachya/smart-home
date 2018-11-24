"""Define automations for Slack."""
# pylint: disable=attribute-defined-outside-init,too-few-public-methods
# pylint: disable=unused-argument,unused-import

import json
from zlib import adler32

from typing import Any, Callable, Dict, Union  # noqa

from automation import Base  # type: ignore
from util import grammatical_list_join, relative_search_dict  # type: ignore

TOGGLE_MAP = {
    'Christmas Tree 🎄': 'switch.christmas_tree',
    'Media Center 🍿': 'switch.media_center',
    'PS4 🎮': 'switch.ps4',
}


def message(response_url: str, text: str, attachments: list = None) -> None:
    """Send a response via the Slack app."""
    import requests

    payload = {'text': text}  # type: Dict[str, Union[str, list]]
    if attachments:
        payload['attachments'] = attachments

    requests.post(
        response_url,
        headers={'Content-Type': 'application/json'},
        json=payload)


class SlashCommand:
    """Define a base class for slash commands."""

    def __init__(self, hass: Base, text: str, response_url: str) -> None:
        """Initialize."""
        self._hass = hass
        self._response_url = response_url
        self._text = text

    def execute(self) -> None:
        """Execute the response to the slash command."""
        raise NotImplementedError()

    def message(self, text: str, attachments: list = None) -> None:
        """Send a response via the Slack app."""
        message(self._response_url, text, attachments)


class Security(SlashCommand):
    """Define an object to handle the /security command."""

    def execute(self) -> None:
        """Execute the response to the slash command."""
        if not self._text:
            open_entities = self._hass.security_manager.get_insecure_entities()
            if open_entities:
                self.message(
                    'These entry points are insecure: {0}.'.format(
                        grammatical_list_join(open_entities)))
            else:
                self.message('The house is locked up and secure.')
            return

        if self._text == 'away':
            self._hass.call_service(
                'scene/turn_on', entity_id='scene.depart_home')
            self.message('The house has been fully secured.')
        elif self._text == 'goodnight':
            self._hass.call_service(
                'scene/turn_on', entity_id='scene.good_night')
            self.message('The house has been secured for the evening.')
        elif self._text == 'home':
            sec_mgr = self._hass.security_manager
            sec_mgr.state = sec_mgr.States.home
            self.message('The security system has been set to "Home".')


class Thermostat(SlashCommand):
    """Define an object to handle the /thermostat command."""

    def execute(self) -> None:
        """Execute the response to the slash command."""
        if not self._text:
            if (self._hass.climate_manager.mode ==
                    self._hass.climate_manager.Modes.eco):
                text = 'The thermostat is set to eco mode.'
            else:
                text = 'The thermostat is set to {0} to {1}°.'.format(
                    self._hass.climate_manager.mode.name,
                    self._hass.climate_manager.indoor_temp)

            self.message(
                '{0} (current indoor temperature: {1}°)'.format(
                    text,
                    self._hass.climate_manager.average_indoor_temperature))
            return

        self._hass.climate_manager.set_indoor_temp(int(self._text))
        self.message("I've set the thermostat to {0}°.".format(self._text))


class ToggleEntity(SlashCommand):
    """Define an object to handle the /toggle command."""

    def execute(self) -> None:
        """Execute the response to the slash command."""
        tokens = self._text.split(' ')

        if 'on' in tokens:
            state = 'on'
            tokens.remove('on')
        elif 'off' in tokens:
            state = 'off'
            tokens.remove('off')
        else:
            self.message("Didn't find either \"on\" or \"off\".")
            return

        target = ' '.join(tokens)
        key, entity = relative_search_dict(TOGGLE_MAP, target)

        if not entity:
            self.message("I'm sorry, I don't know \"{0}\".".format(target))
            return

        method = getattr(self._hass, 'turn_{0}'.format(state))
        method(entity)
        self.message("I've turned \"{0}\" {1}.".format(key, state))


class SlackApp(Base):
    """Define a class to interact with a Slack app."""

    COMMAND_MAP = {
        'security': Security,
        'thermostat': Thermostat,
        'toggle': ToggleEntity,
    }

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self._interactive_command_actions = {}  # type: Dict[str, dict]

        self.listen_event(
            self._interactive_command_received,
            self.properties['interactive_command_event'])
        self.listen_event(
            self.slash_command_received,
            self.properties['slash_command_event'])

    def _interactive_command_received(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to an interactive command."""
        payload = json.loads(data['payload'])
        response_value = payload['actions'][0]['value']
        response_url = payload['response_url']

        if response_value not in self._interactive_command_actions:
            self.error('Unknown response: {0}'.format(response_value))
            return

        parameters = self._interactive_command_actions[response_value]
        callback = parameters.get('callback')
        response_text = parameters.get('response_text')

        if callback:
            callback()

        if response_text:
            message(response_url, response_text)

        self._interactive_command_actions = {}

    def ask(
            self,
            question: str,
            actions: dict,
            *,
            urgent: bool = False,
            image_url: str = None) -> None:
        """Ask a question on Slack (with an optional image)."""
        self._interactive_command_actions = actions

        command_id = adler32(question.encode('utf-8'))

        attachments = [{
            'fallback': '',
            'callback_id': 'interactive_command_{0}'.format(command_id),
            'actions': [{
                'name': '{0}_{1}'.format(command_id, action),
                'text': action,
                'type': 'button',
                'value': action
            } for action in actions]
        }]

        if image_url:
            attachments.append({'title': '', 'image_url': image_url})

        kwargs = {
            'data': {
                'attachments': attachments
            },
            'target': 'slack',
        }  # type: Dict[str, Any]

        if urgent:
            kwargs['blackout_end_time'] = None
            kwargs['blackout_start_time'] = None

        self.notification_manager.send(question, **kwargs)

    def slash_command_received(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond to slash commands."""
        command = data['command'][1:]

        if command not in self.COMMAND_MAP:
            self.error('Unknown slash command: {0}'.format(command))
            return

        self.log(
            'Running Slack slash command: {0} {1}'.format(
                data['command'], data['text']))

        slash_command = self.COMMAND_MAP[command](
            self, data['text'], data['response_url'])
        slash_command.execute()
