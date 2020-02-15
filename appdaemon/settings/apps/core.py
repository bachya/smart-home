"""Define a generic object which  all apps/automations inherit from."""
from datetime import timedelta
from typing import Any, Dict, Union

import voluptuous as vol
from appdaemon.plugins.hass.hassapi import Hass
from helpers import config_validation as cv

CONF_APP = "app"
CONF_CLASS = "class"
CONF_DEPENDENCIES = "dependencies"
CONF_DISABLE = "disable"
CONF_ENABLE = "enable"
CONF_ENABLED_TOGGLE_ENTITY_ID = "enabled_toggle_entity_id"
CONF_INITIAL = "initial"
CONF_MODULE = "module"
CONF_NAME = "name"

APP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODULE): cv.string,
        vol.Required(CONF_CLASS): cv.string,
        vol.Optional(CONF_DEPENDENCIES, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_APP): cv.string,
        vol.Optional(CONF_ENABLED_TOGGLE_ENTITY_ID): cv.entity_id,
    },
    extra=vol.ALLOW_EXTRA,
)


class Base(Hass):  # pylint: disable=too-many-public-methods
    """Define a base app/automation object."""

    APP_SCHEMA = APP_SCHEMA

    def initialize(self) -> None:
        """Initialize."""
        try:
            self.args = self.APP_SCHEMA(self.args)  # type: ignore
        except vol.Invalid as err:
            self.log("Invalid app schema: %s", err, level="ERROR")
            return

        # Define an attribute for the app to store data in:
        self.data = {}  # type: Dict[str, Any]

        # Take every dependency and create a reference to it:
        for app in self.args[CONF_DEPENDENCIES]:
            if not getattr(self, app, None):
                setattr(self, app, self.get_app(app))

        # Define a reference to the "manager app" – for example, a trash-
        # related app might carry a reference to TrashManager:
        if self.args.get(CONF_APP):
            self.app = getattr(self, self.args[CONF_APP])

        # Set the entity ID of the input boolean that will control whether
        # this app is enabled or not:
        if self.args.get(CONF_ENABLED_TOGGLE_ENTITY_ID):
            self._enabled_toggle_entity_id = self.args[CONF_ENABLED_TOGGLE_ENTITY_ID]
        else:
            self._enabled_toggle_entity_id = f"input_boolean.{self.name}"

        # Register custom constraints:
        self.register_constraint("constrain_anyone")
        self.register_constraint("constrain_dark_outside")
        self.register_constraint("constrain_enabled")
        self.register_constraint("constrain_everyone")
        self.register_constraint("constrain_in_bed")
        self.register_constraint("constrain_mode_off")
        self.register_constraint("constrain_mode_on")
        self.register_constraint("constrain_noone")
        self.register_constraint("constrain_sun")

        if self.enabled_entity_exists:
            # If the app has defined callbacks fror when the app is enabled or disabled,
            # attach them to listeners. Note that we utilize `_on_*` here
            # (leading underscore) – we do this so automations don't have to remember
            # callback method signatures:
            if hasattr(self, "on_disable"):
                self.listen_state(
                    self._on_disable, self._enabled_toggle_entity_id, new="off"
                )
            if hasattr(self, "on_enable"):
                self.listen_state(
                    self._on_enable, self._enabled_toggle_entity_id, new="on"
                )

        # Run any initial configuration:
        if hasattr(self, "configure"):
            self.configure()

    @property
    def enabled(self) -> bool:
        """Return whether the app is enabled."""
        if not self.enabled_entity_exists:
            return True
        return self.get_state(self._enabled_toggle_entity_id) == "on"

    @property
    def enabled_entity_exists(self) -> bool:
        """Return True if the enabled entity exists."""
        return self.entity_exists(self._enabled_toggle_entity_id)

    def _constrain_presence(self, method: str, value: Union[str, None]) -> bool:
        """Constrain presence in a generic fashion."""
        if not value:
            return True

        return getattr(self.presence_manager, method)(
            *[self.presence_manager.HomeStates[s] for s in value.split(",")]
        )

    def _on_disable(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Set a listener for when the automation is disabled."""
        self.on_disable()

    def _on_enable(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Set a listener for when the automation is enabled."""
        self.on_enable()

    def constrain_anyone(self, value: str) -> bool:
        """Constrain execution to whether anyone is in a state."""
        return self._constrain_presence("anyone", value)

    def constrain_dark_outside(self, value: bool) -> bool:
        """Constrain execution based whether it's dark outside or not."""
        brightness = float(self.get_state("sensor.filtered_outdoor_brightness"))
        if (value and brightness <= 70) or (not value and brightness > 70):
            return True
        return False

    def constrain_enabled(self, value: bool) -> bool:
        """Constrain execution to whether anyone is in a state."""
        if value:
            return self.enabled
        return False

    def constrain_everyone(self, value: str) -> bool:
        """Constrain execution to whether everyone is in a state."""
        return self._constrain_presence("everyone", value)

    def constrain_in_bed(self, value: bool) -> bool:
        """Constrain execution to whether we're in bed."""
        return value and self.get_state("binary_sensor.in_bed") == "on"

    def constrain_mode_off(self, mode: str) -> bool:
        """Constrain execution to whether a mode is off."""
        return self.get_state(f"input_boolean.{mode}") == "off"

    def constrain_mode_on(self, mode: str) -> bool:
        """Constrain execution to whether a mode is on."""
        return self.get_state(f"input_boolean.{mode}") == "on"

    def constrain_noone(self, value: str) -> bool:
        """Constrain execution to whether no one is in a state."""
        return self._constrain_presence("noone", value)

    def constrain_sun(self, position: str) -> bool:
        """Constrain execution to the location of the sun."""
        if (position == "up" and self.sun_up()) or (
            position == "down" and self.sun_down()
        ):
            return True
        return False

    def disable(self) -> None:
        """Disable the app."""
        if not self.entity_exists(self._enabled_toggle_entity_id):
            return

        self.turn_off(self._enabled_toggle_entity_id)

    def enable(self) -> None:
        """Enable the app."""
        if not self.entity_exists(self._enabled_toggle_entity_id):
            return

        self.turn_on(self._enabled_toggle_entity_id)

    def run_at(self, callback, start, **kwargs):
        """Wrap AppDaemon's `run_at` with a version that handles microsecond resolution.

        Since AD4 has microsecond resolution, calls with a start value of
        self.datetime() will technically be in the past. So, to be safe, bump out the
        start time by a second.
        """
        return super().run_at(callback, start + timedelta(seconds=1), **kwargs)

    def run_every(self, callback, start, interval, **kwargs):
        """Wrap AppDaemon's `run_every` with a version that handles microsecond resolution.

        Since AD4 has microsecond resolution, calls with a start value of
        self.datetime() will technically be in the past. So, to be safe, bump out the
        start time by a second.
        """
        return super().run_every(
            callback, start + timedelta(seconds=1), interval, **kwargs
        )
