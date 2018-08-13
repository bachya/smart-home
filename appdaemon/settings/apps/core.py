"""Define a base object that all apps and automations inherit from."""

# pylint: disable=attribute-defined-outside-init,import-error
# pylint: disable=unused-argument

from typing import Union

import appdaemon.plugins.hass.hassapi as hass  # type: ignore

from const import BLACKOUT_START, BLACKOUT_END  # type: ignore


class Base(hass.Hass):
    """Define a base automation object."""

    def initialize(self) -> None:
        """Initialize."""
        self.entities = self.args.get('entities', {})
        self.handles = {}  # type: ignore
        self.properties = self.args.get('properties', {})

        # Take every dependecy and create a reference to it:
        for app in self.args.get('dependencies', []):
            if not getattr(self, app, None):
                setattr(self, app, self.get_app(app))

        # Register custom constraints:
        self.register_constraint('constrain_anyone')
        self.register_constraint('constrain_blackout')
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
