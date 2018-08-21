"""Define automations for Amazon Dash Buttons."""

# pylint: disable=unused-argument

from automation import Automation  # type: ignore

OPTION_METHOD_MAP = {
    'Activate "Good Night"': ('activate_good_night', {}),
    'Arm security system': ('arm_security_system', {
        'state': 'home'
    }),
    'Toggle Master Bedroom Salt Lamp': (
        'toggle_salt_lamp', {
            'entity_id': 'light.salt_lamp_master_bedroom'
        })
}


class DashAutomation(Automation):
    """Define an automation for Amazon Dash Buttons."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_event(
            self.button_pressed,
            'AMAZON_DASH_PRESS',
            button_label=self.friendly_name)

    def activate_good_night(self) -> None:
        """Turn on the "Good Night" scene."""
        self.turn_on('scene.good_night')

    def arm_security_system(self, state: str) -> None:
        """Set the security system to the specified state."""
        try:
            state_enum = self.security_system.AlarmStates[state]
        except KeyError:
            self.error('Unknown security state: {0}'.format(state))

        self.security_system.state = state_enum

    def toggle_salt_lamp(self, entity_id: str) -> None:
        """Toggle the specified salt lamp."""
        self.call_service('light/toggle', entity_id=entity_id)

    def button_pressed(
            self, event_name: str, data: dict, kwargs: dict) -> None:
        """Respond when button is pressed"""
        action_name = self.get_state(self.entities['action_list'])
        try:
            method, params = OPTION_METHOD_MAP[action_name]
        except (AttributeError, KeyError):
            self.error('Unknown action: {0}'.format(action_name))
            return

        getattr(self, method)(**params)
