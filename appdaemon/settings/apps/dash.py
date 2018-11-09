"""Define automations for Amazon Dash Buttons."""
# pylint: disable=unused-argument

from automation import Automation  # type: ignore

OPTION_METHOD_MAP = {
    'Activate "Good Night"': ('activate_good_night', {}),
    'Arm security system': ('arm_security_system', {
        'state': 'home'
    }),
    'Bump climate 2°': (
        'bump_climate', {
            'amount': 2
        }),
    'Toggle Master Bedroom Salt Lamp': (
        'toggle_salt_lamp', {
            'entity_id': 'light.salt_lamp_master_bedroom'
        })
}


class DashButton(Automation):
    """Define an automation for Amazon Dash Buttons."""

    @property
    def action_list(self) -> str:
        """Return the action input select for this button."""
        return self.entities['action_list']

    @action_list.setter
    def action_list(self, value: str) -> None:
        """Set the action input select for this button."""
        self.select_option(self.entities['action_list'], value)

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_event(
            self.button_pressed,
            'AMAZON_DASH_PRESS',
            button_label=self.properties['friendly_name'])

    def activate_good_night(self) -> None:
        """Turn on the "Good Night" scene."""
        self.turn_on('scene.good_night')

    def arm_security_system(self, state: str) -> None:
        """Set the security system to the specified state."""
        try:
            state_enum = self.security_manager.States[state]
        except KeyError:
            self.error('Unknown security state: {0}'.format(state))

        self.security_manager.state = state_enum

    def bump_climate(self, amount: int) -> None:
        """Bump the climate up or down by a certain amount."""
        if self.climate_manager.mode == self.climate_manager.Modes.cool:
            amount *= -1

        self.climate_manager.indoor_temp += amount

    def toggle_salt_lamp(self, entity_id: str) -> None:
        """Toggle the specified salt lamp."""
        self.call_service('light/toggle', entity_id=entity_id)

    def button_pressed(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond when button is pressed."""
        action_name = self.get_state(self.entities['action_list'])
        try:
            method, params = OPTION_METHOD_MAP[action_name]
        except (AttributeError, KeyError):
            self.error('Unknown action: {0}'.format(action_name))
            return

        getattr(self, method)(**params)
