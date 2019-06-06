"""Define generic automation objects and logic."""
from typing import Callable, Dict, Union  # noqa, pylint: disable=unused-import

import voluptuous as vol
from appdaemon.plugins.hass.hassapi import Hass  # type: ignore

from const import (
    CONF_ICON,
    OPERATOR_ALL,
    OPERATORS,
    THRESHOLD_CLOUDY,
)
from helpers import config_validation as cv

CONF_CLASS = "class"
CONF_MODULE = "module"
CONF_DEPENDENCIES = "dependencies"

CONF_APP = "app"
CONF_CONSTRAINTS = "constraints"

CONF_ENABLED_CONFIG = "enabled_config"
CONF_INITIAL = "initial"
CONF_NAME = "name"
CONF_TOGGLE_NAME = "toggle_name"

CONF_OPERATOR = "operator"

SENSOR_CLOUD_COVER = "sensor.dark_sky_cloud_coverage"

APP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODULE): str,
        vol.Required(CONF_CLASS): str,
        vol.Optional(CONF_DEPENDENCIES): cv.ensure_list,
        vol.Optional(CONF_APP): str,
        vol.Optional(CONF_CONSTRAINTS): vol.Schema(
            {
                vol.Optional(CONF_OPERATOR, default=OPERATOR_ALL): vol.In(
                    OPERATORS
                ),
                vol.Required(CONF_CONSTRAINTS): dict,
            }
        ),
        vol.Optional(CONF_ENABLED_CONFIG): vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_ICON): str,
                vol.Required(CONF_INITIAL): bool,
                vol.Optional(CONF_TOGGLE_NAME): str,
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


class Base(Hass):
    """Define a base automation object."""

    APP_SCHEMA = APP_SCHEMA

    def initialize(self) -> None:
        """Initialize."""
        try:
            self.APP_SCHEMA(self.args)
        except vol.Invalid as err:
            self.error("Invalid app schema: {0}".format(err), level="ERROR")
            return

        # Define a holding place for HASS entity IDs:
        self.entity_ids = self.args.get("entity_ids", {})

        # Define a holding place for any scheduler handles that the automation
        # wants to keep track of:
        self.handles = {}  # type: Dict[str, str]

        # Define a holding place for key/value properties for this automation:
        self.properties = self.args.get("properties", {})

        # Take every dependecy and create a reference to it:
        for app in self.args.get("dependencies", []):
            if not getattr(self, app, None):
                setattr(self, app, self.get_app(app))

        # Define a reference to the "manager app" – for example, a trash-
        # related automation might carry a reference to TrashManager:
        if self.args.get("app"):
            self.app = getattr(self, self.args["app"])

        # Set the entity ID of the input boolean that will control whether
        # this automation is enabled or not:
        self.enabled_entity_id = None  # type: ignore
        enabled_config = self.args.get("enabled_config", {})
        if enabled_config:
            if enabled_config.get("toggle_name"):
                self.enabled_entity_id = "input_boolean.{0}".format(
                    enabled_config["toggle_name"]
                )
            else:
                self.enabled_entity_id = "input_boolean.{0}".format(self.name)

        # Register any "mode alterations" for this automation – for example,
        # perhaps it should be disabled when Vacation Mode is enabled:
        for mode, value in self.args.get("mode_alterations", {}).items():
            mode_app = getattr(self, mode)
            mode_app.register_enabled_entity(self.enabled_entity_id, value)

        # Register custom constraints:
        self.register_constraint("constrain_anyone")
        self.register_constraint("constrain_cloudy")
        self.register_constraint("constrain_everyone")
        self.register_constraint("constrain_in_blackout")
        self.register_constraint("constrain_noone")
        self.register_constraint("constrain_sun")

        # Run any user-specific configuration:
        if hasattr(self, "configure"):
            self.configure()

    def _attach_constraints(
        self, method: Callable, callback: Callable, *args: list, **kwargs: dict
    ) -> Union[str, list]:
        """Attach the constraint mechanism to an AppDaemon listener."""
        if not self.args.get(CONF_CONSTRAINTS):
            return method(callback, *args, **kwargs)

        constraints = self.args[CONF_CONSTRAINTS][CONF_CONSTRAINTS]

        if self.args[CONF_CONSTRAINTS].get(CONF_OPERATOR) == OPERATOR_ALL:
            return method(callback, *args, **constraints, **kwargs)

        handles = []  # type: ignore
        for name, value in constraints.items():
            method(callback, *args, **{name: value}, **kwargs)
        return handles

    def _constrain_presence(
        self, method: str, value: Union[str, None]
    ) -> bool:
        """Constrain presence in a generic fashion."""
        if not value:
            return True

        return getattr(self.presence_manager, method)(
            *[self.presence_manager.HomeStates[s] for s in value.split(",")]
        )

    def constrain_anyone(self, value: str) -> bool:
        """Constrain execution to whether anyone is in a state."""
        return self._constrain_presence("anyone", value)

    def constrain_cloudy(self, value: bool) -> bool:
        """Constrain execution based whether it's cloudy or not."""
        cloud_cover = float(self.get_state(SENSOR_CLOUD_COVER))
        if (value and cloud_cover >= THRESHOLD_CLOUDY) or (
            not value and cloud_cover < THRESHOLD_CLOUDY
        ):
            return True
        return False

    def constrain_everyone(self, value: str) -> bool:
        """Constrain execution to whether everyone is in a state."""
        return self._constrain_presence("everyone", value)

    def constrain_in_blackout(self, state: str) -> bool:
        """Constrain execution based on blackout state."""
        if state is True:
            return self.blackout_mode.in_blackout()

        return not self.blackout_mode.in_blackout()

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

    def listen_ios_event(self, callback: Callable, action: str) -> None:
        """Register a callback for an iOS event."""
        self.listen_event(
            callback,
            "ios.notification_action_fired",
            actionName=action,
            constrain_input_boolean=self.enabled_entity_id,
        )

    def listen_event(
        self, callback, event=None, auto_constraints=False, **kwargs
    ):
        """Wrap AppDaemon's event listener with the constraint mechanism."""
        if not auto_constraints:
            return super().listen_event(callback, event, **kwargs)

        return self._attach_constraints(
            super().listen_event, callback, event, **kwargs
        )

    def listen_state(
        self, callback, entity=None, auto_constraints=False, **kwargs
    ):
        """Wrap AppDaemon's state listener with the constraint mechanism."""
        if not auto_constraints:
            return super().listen_state(callback, entity, **kwargs)

        return self._attach_constraints(
            super().listen_state, callback, entity, **kwargs
        )

    def run_daily(self, callback, start, auto_constraints=False, **kwargs):
        """Wrap AppDaemon's daily run with the constraint mechanism."""
        if not auto_constraints:
            return super().run_daily(callback, start, **kwargs)

        return self._attach_constraints(
            super().run_daily, callback, start, **kwargs
        )

    def run_at_sunrise(
        self, callback, *args, auto_constraints=False, **kwargs
    ):
        """Wrap AppDaemon's sunrise run with the constraint mechanism."""
        if not auto_constraints:
            return super().run_at_sunrise(callback, **kwargs)

        return self._attach_constraints(
            super().run_at_sunrise, callback, **kwargs
        )

    def run_at_sunset(
        self,
        callback: Callable[..., None],
        *args: list,
        auto_constraints=False,
        **kwargs: dict
    ):
        """Wrap AppDaemon's sunset run with the constraint mechanism."""
        if not auto_constraints:
            return super().run_at_sunset(callback, **kwargs)

        return self._attach_constraints(
            super().run_at_sunset, callback, **kwargs
        )

    def run_every(
        self, callback, start, interval, auto_constraints=False, **kwargs
    ):
        """Wrap AppDaemon's everday run with the constraint mechanism."""
        if not auto_constraints:
            return super().run_every(callback, start, interval, **kwargs)

        return self._attach_constraints(
            super().run_every, callback, start, interval, **kwargs
        )
