"""Define automations for Amazon Dash Buttons."""
# pylint: disable=too-few-public-methods
from typing import List, Optional, Union
import voluptuous as vol

from const import CONF_ENTITY_ID, CONF_ENTITY_IDS, CONF_FRIENDLY_NAME, CONF_PROPERTIES
from core import APP_SCHEMA, Base
from helpers import config_validation as cv

BUTTON_ACTION_NO_ACTION = "<none>"

BUTTON_ACTION_BUMP_CLIMATE_2_DEGREES = "Bump Climate 2°"
BUTTON_ACTION_GOOD_NIGHT = 'Activate "Good Night"'
BUTTON_ACTION_SECURITY_HOME = 'Arm Security System "Home"'
BUTTON_ACTION_TOGGLE_ALL_SALT_LAMPS = "Toggle All Salt Lamps"
BUTTON_ACTION_TOGGLE_CHRISTMAS_TREE = "Toggle Christmas Money"
BUTTON_ACTION_TOGGLE_LIVING_ROOM_LIGHTS = "Toggle Living Room Lights"
BUTTON_ACTION_TOGGLE_CLIMATE = "Toggle Climate"

CONF_ACTION_LIST = "action_list"
CONF_SCENE_DATA = "scene_data"
CONF_SCENE_ID = "scene_id"


class ButtonAction:
    """Define a generic button action."""

    def run(self) -> None:
        """Run."""
        raise NotImplementedError()


class ActivateScene(ButtonAction):
    """Define an action that turns on a scene."""

    def __init__(self, app: Base, scene: str) -> None:
        """Build the action."""
        self._app = app
        self._scene = scene

    def run(self) -> None:
        """Turn on the scene."""
        self._app.turn_on(f"scene.{self._scene}")


class BumpClimate(ButtonAction):
    """Define an action that bumps the climate X° in the correct direction."""

    def __init__(self, app: Base, degrees: int) -> None:
        """Build the action."""
        self._app = app
        self._degrees = degrees

    def run(self) -> None:
        """Bump."""
        self._app.climate_manager.bump_temperature(self._degrees)


class SetSecuritySystem(ButtonAction):
    """Define an action that sets the security system."""

    def __init__(self, app: Base, state: str) -> None:
        """Build the action."""
        self._app = app
        self._state = state

    def run(self) -> None:
        """Set the security system."""
        self._app.security_manager.set_alarm(
            self._app.security_manager.AlarmStates[self._state]
        )


class ToggleClimate(ButtonAction):
    """Define an action that toggles the thermostat between off and its prev. state."""

    def __init__(self, app: Base) -> None:
        """Build the action."""
        self._app = app

    def run(self) -> None:
        """Toggle."""
        self._app.climate_manager.toggle()


class ToggleEntity(ButtonAction):
    """Toggle an entity."""

    def __init__(
        self, app: Base, entity: Union[str, List[str]], master: Optional[str] = None
    ) -> None:
        """Build the action."""
        self._app = app
        if isinstance(entity, list):
            self._entity = entity
        else:
            self._entity = [entity]
        self._master = master

    def run(self) -> None:
        """Toggle."""
        if self._master:
            if self._app.get_state(self._master) == "on":
                method_name = "turn_off"
            else:
                method_name = "turn_on"
        else:
            method_name = "toggle"

        method = getattr(self._app, method_name)
        for entity_id in self._entity:
            method(entity_id)


class Button(Base):
    """Define a generic button."""

    def configure(self) -> None:
        """Configure."""
        raise NotImplementedError()

    def _on_button_press(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond when button is pressed."""
        action_name = self.get_state(self.entity_ids[CONF_ACTION_LIST])

        if action_name == BUTTON_ACTION_NO_ACTION:
            return

        action: ButtonAction
        if action_name == BUTTON_ACTION_BUMP_CLIMATE_2_DEGREES:
            action = BumpClimate(self, 2)
        elif action_name == BUTTON_ACTION_GOOD_NIGHT:
            action = ActivateScene(self, "good_night")
        elif action_name == BUTTON_ACTION_SECURITY_HOME:
            action = SetSecuritySystem(self, "home")
        elif action_name == BUTTON_ACTION_TOGGLE_ALL_SALT_LAMPS:
            action = ToggleEntity(
                self,
                ["switch.office_salt_lamp", "switch.master_bedroom_salt_lamp"],
                master="switch.master_bedroom_salt_lamp",
            )
        elif action_name == BUTTON_ACTION_TOGGLE_CHRISTMAS_TREE:
            action = ToggleEntity(self, "switch.christmas_tree")
        elif action_name == BUTTON_ACTION_TOGGLE_CLIMATE:
            action = ToggleClimate(self)
        elif action_name == BUTTON_ACTION_TOGGLE_LIVING_ROOM_LIGHTS:
            action = ToggleEntity(self, "group.living_room_lights")
        else:
            self.error("Unknown button action: %s", action_name)
            return

        self.log("Running action: %s", action_name)
        action.run()


class AmazonDashButton(Button):
    """Define an Amazon Dash button."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {vol.Required(CONF_ACTION_LIST): cv.entity_id}, extra=vol.ALLOW_EXTRA
            ),
            CONF_PROPERTIES: vol.Schema(
                {vol.Required(CONF_FRIENDLY_NAME): str}, extra=vol.ALLOW_EXTRA
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self._on_button_press,
            "AMAZON_DASH_PRESS",
            button_label=self.properties[CONF_FRIENDLY_NAME],
        )


class ZWaveButton(Button):
    """Define a Z-Wave button."""

    APP_SCHEMA = APP_SCHEMA.extend(
        {
            CONF_ENTITY_IDS: vol.Schema(
                {
                    vol.Required(CONF_ENTITY_ID): cv.entity_id,
                    vol.Required(CONF_ACTION_LIST): cv.entity_id,
                },
                extra=vol.ALLOW_EXTRA,
            ),
            CONF_PROPERTIES: vol.Schema(
                {vol.Required(CONF_SCENE_ID): int, vol.Required(CONF_SCENE_DATA): int},
                extra=vol.ALLOW_EXTRA,
            ),
        }
    )

    def configure(self) -> None:
        """Configure."""
        self.listen_event(
            self._on_button_press,
            "zwave.scene_activated",
            scene_id=self.properties[CONF_SCENE_ID],
            scene_data=self.properties[CONF_SCENE_DATA],
        )
