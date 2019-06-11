"""Define a generic object which  all apps/automations inherit from."""
from typing import Callable, Dict, List, Union

import voluptuous as vol
from appdaemon.plugins.hass.hassapi import Hass  # pylint: disable=no-name-in-module

from const import (
    CONF_ENTITY_IDS,
    CONF_PROPERTIES,
    EVENT_MODE_CHANGE,
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
CONF_MODE_ALTERATIONS = "mode_alterations"

CONF_ENABLED_TOGGLE_ENTITY_ID = "enabled_toggle_entity_id"
CONF_INITIAL = "initial"
CONF_NAME = "name"

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
                vol.Optional(CONF_OPERATOR, default=OPERATOR_ALL): vol.In(OPERATORS),
                vol.Required(CONF_CONSTRAINTS): dict,
            }
        ),
        vol.Optional(CONF_ENABLED_TOGGLE_ENTITY_ID): str,
    },
    extra=vol.ALLOW_EXTRA,
)


class Base(Hass):
    """Define a base app/automation object."""

    APP_SCHEMA = APP_SCHEMA

    def initialize(self) -> None:
        """Initialize."""
        try:
            self.APP_SCHEMA(self.args)
        except vol.Invalid as err:
            self.error("Invalid app schema: {0}".format(err), level="ERROR")
            return

        # Define a holding place for HASS entity IDs:
        self.entity_ids = self.args.get(CONF_ENTITY_IDS, {})

        # Define a holding place for any scheduler handles that the app wants to keep
        # track of:
        self.handles = {}  # type: Dict[str, Callable]

        # Define a holding place for key/value properties for this app:
        self.properties = self.args.get(CONF_PROPERTIES, {})

        # Define a holding place for any mode alterations for this app:
        self.mode_alterations = self.args.get(CONF_MODE_ALTERATIONS, [])

        # Take every dependecy and create a reference to it:
        for app in self.args.get(CONF_DEPENDENCIES, []):
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
            self._enabled_toggle_entity_id = "input_boolean.{0}".format(self.name)

        if self._enabled_entity_exists():
            # Listen and track mode changes so that the app can respond as needed:
            self.mode_events = []  # type: List[str]
            self.listen_event(self._on_mode_change, EVENT_MODE_CHANGE)

            # If the app has defined callbacks fror when the app is enabled or disabled,
            # attach them to listeners:
            if getattr(self, "on_disable", None):
                super().listen_state(
                    self.on_disable, self._enabled_toggle_entity_id, new="off"
                )
            if getattr(self, "on_enable", None):
                super().listen_state(
                    self._on_enable, self._enabled_toggle_entity_id, new="on"
                )

        # Register custom constraints:
        self.register_constraint("constrain_anyone")
        self.register_constraint("constrain_cloudy")
        self.register_constraint("constrain_enabled")
        self.register_constraint("constrain_everyone")
        self.register_constraint("constrain_in_blackout")
        self.register_constraint("constrain_noone")
        self.register_constraint("constrain_sun")

        # Run any addutional configuration:
        if hasattr(self, "configure"):
            self.configure()

    @property
    def enabled(self) -> bool:
        """Return whether the app is enabled."""
        if not self._enabled_entity_exists():
            return True
        return self.get_state(self._enabled_toggle_entity_id) == "on"

    def _attach_constraints(
        self, method: Callable, callback: Callable, *args: list, **kwargs: dict
    ) -> Union[str, list]:
        """Attach the constraint mechanism to an AppDaemon listener."""
        if not self.args.get(CONF_CONSTRAINTS):
            return method(callback, *args, **kwargs)

        constraints = self.args[CONF_CONSTRAINTS][CONF_CONSTRAINTS]

        if self.args[CONF_CONSTRAINTS].get(CONF_OPERATOR) == OPERATOR_ALL:
            return method(callback, *args, **constraints, **kwargs)

        handles = []  # type: List[str]
        for name, value in constraints.items():
            method(callback, *args, **{name: value}, **kwargs)
        return handles

    def _constrain_presence(self, method: str, value: Union[str, None]) -> bool:
        """Constrain presence in a generic fashion."""
        if not value:
            return True

        return getattr(self.presence_manager, method)(
            *[self.presence_manager.HomeStates[s] for s in value.split(",")]
        )

    def _enabled_entity_exists(self) -> bool:
        """Return True if the enabled entity exists."""
        return self.entity_exists(self._enabled_toggle_entity_id)

    def _on_mode_change(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Compare mode changes to registered mode alterations."""
        mode = data["name"]

        if data["state"] == "on":
            self.mode_events.append(mode)
        elif mode in self.mode_events:
            self.mode_events.remove(mode)

        try:
            primary = max(
                (m for m in self.mode_alterations if m["mode"] in self.mode_events),
                key=lambda m: m["priority"],
            )
        except ValueError:
            try:
                primary = next((m for m in self.mode_alterations if m["mode"] == mode))
            except StopIteration:
                return

            if primary["action"] == "enable":
                primary["action"] = "disable"
            else:
                primary["action"] = "enable"

        # If the primary mode alteration prescribes an action that matches the state the
        # app is already in, return:
        if (self.enabled and primary["action"] == "enable") or (
            not self.enabled and primary["action"] == "disable"
        ):
            return

        if primary["action"] == "enable":
            self.enable()
        else:
            self.disable()

    def constrain_anyone(self, value: str) -> bool:
        """Constrain execution to whether anyone is in a state."""
        return self._constrain_presence("anyone", value)

    def constrain_enabled(self, value: bool) -> bool:
        """Constrain execution to whether anyone is in a state."""
        if value:
            return self.enabled
        return False

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

    def listen_ios_event(self, callback: Callable, action: str) -> None:
        """Register a callback for an iOS event."""
        self.listen_event(
            callback,
            "ios.notification_action_fired",
            actionName=action,
            constrain_enabled=True,
        )

    def listen_event(self, callback, event=None, auto_constraints=False, **kwargs):
        """Wrap AppDaemon's `listen_event` with the constraint mechanism."""
        if not auto_constraints:
            return super().listen_event(callback, event, **kwargs)

        return self._attach_constraints(super().listen_event, callback, event, **kwargs)

    def listen_state(self, callback, entity=None, auto_constraints=False, **kwargs):
        """Wrap AppDaemon's `listen_state` with the constraint mechanism."""
        if not auto_constraints:
            return super().listen_state(callback, entity, **kwargs)

        return self._attach_constraints(
            super().listen_state, callback, entity, **kwargs
        )

    def run_daily(self, callback, start, auto_constraints=False, **kwargs):
        """Wrap AppDaemon's `run_daily` with the constraint mechanism."""
        if not auto_constraints:
            return super().run_daily(callback, start, **kwargs)

        return self._attach_constraints(super().run_daily, callback, start, **kwargs)

    def run_at_sunrise(self, callback, *args, auto_constraints=False, **kwargs):
        """Wrap AppDaemon's `run_at_sunrise` with the constraint mechanism."""
        if not auto_constraints:
            return super().run_at_sunrise(callback, **kwargs)

        return self._attach_constraints(super().run_at_sunrise, callback, **kwargs)

    def run_at_sunset(
        self,
        callback: Callable[..., None],
        *args: list,
        auto_constraints=False,
        **kwargs: dict
    ):
        """Wrap AppDaemon's `run_at_sunset` with the constraint mechanism."""
        if not auto_constraints:
            return super().run_at_sunset(callback, **kwargs)

        return self._attach_constraints(super().run_at_sunset, callback, **kwargs)

    def run_every(self, callback, start, interval, auto_constraints=False, **kwargs):
        """Wrap AppDaemon's `run_every` with the constraint mechanism."""
        if not auto_constraints:
            return super().run_every(callback, start, interval, **kwargs)

        return self._attach_constraints(
            super().run_every, callback, start, interval, **kwargs
        )
