"""Define automations for Slack."""
import json
from typing import Dict, Optional, Union
from zlib import adler32

import requests

from core import Base
from helpers import (
    grammatical_list_join,
    random_affirmative_response,
    relative_search_list,
)
from helpers.notification import send_notification


def message(response_url: str, text: str, attachments: list = None) -> None:
    """Send a response via the Slack app."""
    payload = {"text": text}  # type: Dict[str, Union[str, list]]
    if attachments:
        payload["attachments"] = attachments

    requests.post(
        response_url, headers={"Content-Type": "application/json"}, json=payload
    )


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
                    (
                        "These entry points are insecure: "
                        f"{grammatical_list_join(open_entities)}."
                    )
                )
            else:
                self.message("The house is locked up and secure.")
            return

        if self._text == "away":
            self._hass.call_service("scene/turn_on", entity_id="scene.depart_home")
            self.message("The house has been fully secured.")
        elif self._text == "goodnight":
            self._hass.call_service("scene/turn_on", entity_id="scene.good_night")
            self.message("The house has been secured for the evening.")
        elif self._text == "home":
            sec_mgr = self._hass.security_manager
            sec_mgr.state = sec_mgr.States.home
            self.message("The security system has been set to `Home`.")


class Thermostat(SlashCommand):
    """Define an object to handle the /thermostat command."""

    def execute(self) -> None:
        """Execute the response to the slash command."""
        if not self._text:
            text = (
                f"The thermostat is set to `{self._hass.climate_manager.hvac_mode}` "
                f"to `{self._hass.climate_manager.target_temperature}°`."
            )

            self.message(
                (
                    f"{text} The current indoor temperature is "
                    f"`{self._hass.climate_manager.indoor_temperature}°`."
                )
            )
            return

        self._hass.climate_manager.set_temperature(int(self._text))
        self.message(f"I've set the thermostat to `{self._text}°`.")


class Toggle(SlashCommand):
    """Define an object to handle the /toggle command."""

    def execute(self) -> None:
        """Execute the response to the slash command."""
        entity_ids = [
            entity_id
            for domain in self._hass.properties["toggle_domains"]
            for entity_id in self._hass.get_state(domain).keys()
        ]

        tokens = self._text.split(" ")

        new_state = None  # type: Optional[str]
        if "on" in tokens:
            method_name = "turn_on"
            new_state = "on"
            tokens.remove("on")
        elif "off" in tokens:
            method_name = "turn_off"
            new_state = "off"
            tokens.remove("off")
        else:
            method_name = "toggle"

        target = "_".join(tokens)
        entity_id = relative_search_list(entity_ids, target)

        if new_state is None:
            if self._hass.get_state(entity_id) == "on":
                new_state = "off"
            else:
                new_state = "on"

        try:
            method = getattr(self._hass, method_name)
            method(entity_id)
            response = random_affirmative_response(replace_hyphens=False)

            self.message(f"{response} `{entity_id}` is now `{new_state}`.")
        except (TypeError, ValueError):
            self.message(f"Sorry: I don't know what `{target}` is.")


class SlackApp(Base):
    """Define a class to interact with a Slack app."""

    COMMAND_MAP = {"security": Security, "thermostat": Thermostat, "toggle": Toggle}

    def configure(self) -> None:
        """Configure."""
        self._interactive_command_actions = {}  # type: Dict[str, dict]

        self.listen_event(
            self._on_interactive_command_received,
            self.args["interactive_command_event"],
        )
        self.listen_event(
            self._on_slash_command_received, self.args["slash_command_event"]
        )

    def _on_interactive_command_received(
        self, event_name: str, data: dict, kwargs: dict
    ) -> None:
        """Respond to an interactive command."""
        payload = json.loads(data["payload"])
        response_value = payload["actions"][0]["value"]
        response_url = payload["response_url"]

        if response_value not in self._interactive_command_actions:
            self.error("Unknown response: %s", response_value)
            return

        parameters = self._interactive_command_actions[response_value]
        callback = parameters.get("callback")
        response_text = parameters.get("response_text")

        if callback:
            callback()

        if response_text:
            message(response_url, response_text)

        self._interactive_command_actions = {}

    def _on_slash_command_received(
        self, event_name: str, data: dict, kwargs: dict
    ) -> None:
        """Respond to slash commands."""
        command = data["command"][1:]

        if command not in self.COMMAND_MAP:
            self.error("Unknown slash command: %s", command)
            return

        self.log("Running Slack slash command: %s %s", data["command"], data["text"])

        slash_command = self.COMMAND_MAP[command](
            self, data["text"], data["response_url"]
        )
        slash_command.execute()

    def ask(
        self,
        question: str,
        actions: dict,
        *,
        urgent: bool = False,
        image_url: str = None,
    ) -> None:
        """Ask a question on Slack (with an optional image)."""
        self._interactive_command_actions = actions

        command_id = adler32(question.encode("utf-8"))

        attachments = [
            {
                "fallback": "",
                "callback_id": f"interactive_command_{command_id}",
                "actions": [
                    {
                        "name": f"{command_id}_{action}",
                        "text": action,
                        "type": "button",
                        "value": action,
                    }
                    for action in actions
                ],
            }
        ]

        if image_url:
            attachments.append({"title": "", "image_url": image_url})

        send_notification(self, "slack", question, data={"attachments": attachments})
