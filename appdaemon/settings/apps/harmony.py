"""Define an app for working the Living Room TV."""

# pylint: disable=attribute-defined-outside-init

from typing import Union

from app import App  # type: ignore


class HarmonyRemote(App):
    """Define a class to represent the Living Room TV."""

    @property
    def current_activity_id(self) -> Union[int, None]:
        """Get the current activity ID (Harmony)."""
        activity = self.get_state(self.entity, attribute='current_activity')
        try:
            return self.activities[activity.replace(' ', '_').lower()]
        except KeyError:
            return None

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.activities = self.args['activities']
        self.entity = self.args['entity']

    def send_command(self, command: str) -> None:
        """Send a command to the Harmony."""
        if self.current_activity_id:
            self.call_service(
                'remote/send_command',
                entity_id=self.entity,
                device=self.current_activity_id,
                command=command)

    def pause(self) -> None:
        """Pause the entire thing by pausing the Harmony."""
        self.send_command('Pause')

    def play(self) -> None:
        """Play the entire thing by playing the Harmony."""
        self.send_command('Play')
