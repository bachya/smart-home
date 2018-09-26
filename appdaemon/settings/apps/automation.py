"""Define generic automation objects and logic."""

# pylint: disable=attribute-defined-outside-init,import-error

from typing import Callable, Dict, Union  # noqa, pylint: disable=unused-import

from appdaemon.plugins.hass.hassapi import Hass  # type: ignore

from const import (  # type: ignore
    BLACKOUT_START, BLACKOUT_END, THRESHOLD_CLOUDY)

SENSOR_CLOUD_COVER = 'sensor.dark_sky_cloud_coverage'


class Base(Hass):
    """Define a base automation object."""

    def initialize(self) -> None:
        """Initialize."""
        # Define a holding place for HASS entity IDs:
        self.entities = self.args.get('entities', {})

        # Define a holding place for any scheduler handles that the automation
        # wants to keep track of:
        self.handles = {}  # type: Dict[str, str]

        # Define a holding place for key/value properties for this automation:
        self.properties = self.args.get('properties', {})

        # Take every dependecy and create a reference to it:
        for app in self.args.get('dependencies', []):
            if not getattr(self, app, None):
                setattr(self, app, self.get_app(app))

        # Register custom constraints:
        self.register_constraint('constrain_anyone')
        self.register_constraint('constrain_blackout')
        self.register_constraint('constrain_cloudy')
        self.register_constraint('constrain_everyone')
        self.register_constraint('constrain_noone')
        self.register_constraint('constrain_sun')

    def _constrain_presence(self, method: str,
                            value: Union[str, None]) -> bool:
        """Constrain presence in a generic fashion."""
        if not value:
            return True

        return getattr(self.presence_manager, method)(
            *[self.presence_manager.HomeStates[s] for s in value.split(',')])

    def constrain_anyone(self, value: str) -> bool:
        """Constrain execution to whether anyone is in a state."""
        return self._constrain_presence('anyone', value)

    def constrain_blackout(self, state: str) -> bool:
        """Constrain execution based on blackout state."""
        if state not in ['in', 'out']:
            raise ValueError('Unknown blackout state: {0}'.format(state))

        in_blackout = self.now_is_between(BLACKOUT_START, BLACKOUT_END)
        if state == 'in':
            return in_blackout
        return not in_blackout

    def constrain_cloudy(self, value: bool) -> bool:
        """Constrain execution based whether it's cloudy or not."""
        cloud_cover = float(self.get_state(SENSOR_CLOUD_COVER))
        if (value and cloud_cover >= THRESHOLD_CLOUDY) or (
                not value and cloud_cover < THRESHOLD_CLOUDY):
            return True
        return False

    def constrain_everyone(self, value: str) -> bool:
        """Constrain execution to whether everyone is in a state."""
        return self._constrain_presence('everyone', value)

    def constrain_noone(self, value: str) -> bool:
        """Constrain execution to whether no one is in a state."""
        return self._constrain_presence('noone', value)

    def constrain_sun(self, position: str) -> bool:
        """Constrain execution to the location of the sun."""
        if ((position == 'up' and self.sun_up())
                or (position == 'down' and self.sun_down())):
            return True
        return False


class Automation(Base):
    """Define a base automation object."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        # Define a reference to the "manager app" – for example, a trash-
        # related automation might carry a reference to TrashManager:
        if self.args.get('app'):
            self.app = getattr(self, self.args['app'])

        # Set the entity ID of the input boolean that will control whether
        # this automation is enabled or not:
        self.enabled_entity_id = None  # type: ignore
        enabled_config = self.args.get('enabled_config', {})
        if enabled_config:
            if enabled_config.get('entity_name'):
                self.enabled_entity_id = 'input_boolean.{0}'.format(
                    enabled_config['entity_name'])
            else:
                self.enabled_entity_id = 'input_boolean.{0}'.format(self.name)

        # Register any "mode alterations" for this automation – for example,
        # perhaps it should be disabled when Vacation Mode is enabled:
        mode_alterations = self.args.get('mode_alterations', {})
        if mode_alterations:
            for mode, value in mode_alterations.items():
                mode_app = getattr(self, mode)
                mode_app.register_enabled_entity(self.enabled_entity_id, value)

    def listen_ios_event(self, callback: Callable, action: str) -> None:
        """Register a callback for an iOS event."""
        self.listen_event(
            callback,
            'ios.notification_action_fired',
            actionName=action,
            constrain_input_boolean=self.enabled_entity_id)
