"""Define automations for Slack."""
# pylint: disable=attribute-defined-outside-init,too-few-public-methods
# pylint: disable=unused-argument,unused-import

import json
from zlib import adler32

from typing import Any, Callable, Dict, Union  # noqa

from automation import Base  # type: ignore
from util import (
    grammatical_list_join, random_affirmative_response,
    relative_search_list)  # type: ignore


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
            self.message('The security system has been set to `Home`.')


class Thermostat(SlashCommand):
    """Define an object to handle the /thermostat command."""

    def execute(self) -> None:
        """Execute the response to the slash command."""
        if not self._text:
            if (self._hass.climate_manager.mode ==
                    self._hass.climate_manager.Modes.eco):
                text = 'The thermostat is set to eco mode.'
            else:
                text = 'The thermostat is set to `{0}` to `{1}°`.'.format(
                    self._hass.climate_manager.mode.name,
                    self._hass.climate_manager.indoor_temp)

            self.message(
                '{0} The current indoor temperature is `{1}°`.'.format(
                    text,
                    self._hass.climate_manager.average_indoor_temperature))
            return

        self._hass.climate_manager.set_indoor_temp(int(self._text))
        self.message("I've set the thermostat to `{0}°`.".format(self._text))


class Toggle(SlashCommand):
    """Define an object to handle the /toggle command."""

    def execute(self) -> None:
        """Execute the response to the slash command."""
        entity_ids = [
            entity_id for domain in self._hass.properties['toggle_domains']
            for entity_id in self._hass.get_state(domain).keys()
        ]

        tokens = self._text.split(' ')

        if 'on' in tokens:
            method_name = 'turn_on'
            new_state = 'on'
            tokens.remove('on')
        elif 'off' in tokens:
            method_name = 'turn_off'
            new_state = 'off'
            tokens.remove('off')
        else:
            method_name = 'toggle'
            new_state = None  # type: ignore

        target = '_'.join(tokens)
        entity_id = relative_search_list(entity_ids, target)

        if new_state is None:
            if self._hass.get_state(entity_id) == 'on':
                new_state = 'off'
            else:
                new_state = 'on'

        try:
            method = getattr(self._hass, method_name)
            method(entity_id)
            self.message(
                '{0} `{1}` is now `{2}`.'.format(
                    random_affirmative_response(replace_hyphens=False),
                    entity_id,
                    new_state))
        except (TypeError, ValueError):
            self.message("Sorry: I don't know what `{0}` is.".format(target))


class SlackApp(Base):
    """Define a class to interact with a Slack app."""

    COMMAND_MAP = {
        'security': Security,
        'thermostat': Thermostat,
        'toggle': Toggle,
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

        self._log.info(
            'Running Slack slash command: %s %s', data['command'],
            data['text'])

        slash_command = self.COMMAND_MAP[command](
            self, data['text'], data['response_url'])
        slash_command.execute()
