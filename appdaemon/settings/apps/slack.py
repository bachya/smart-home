"""Define automations for Slack."""
# pylint: disable=attribute-defined-outside-init,unused-argument

import requests

from automation import Base  # type: ignore


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
            method = getattr(self, data['name'])
            method(data)
        except AttributeError:
            self.error(
                'No implementation of slash command handler: {0}'.format(
                    data['name']))

    def thermostat(self, data: dict) -> None:
        """Alter the thermostat."""
        target_temp = data['text']

        if target_temp:
            self.climate_manager.indoor_temp = int(target_temp)
            self._respond(
                "I've set the thermostat to {0}°.".format(target_temp))
        else:
            self._respond(
                'The thermostat is currently set to {0}° '
                '(current indoor temperature: {1}°).'.
                format(
                    self.climate_manager.indoor_temp,
                    self.climate_manager.average_indoor_temperature))
