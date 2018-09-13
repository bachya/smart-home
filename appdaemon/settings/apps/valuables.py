"""Define automations for our valuables."""

# pylint: disable=unused-argument

from automation import Automation  # type: ignore


class LeftSomewhere(Automation):
    """Define a feature to notify when a Tile has been left somewhere."""

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        self.listen_event(
            self.arrived_home,
            'PRESENCE_CHANGE',
            person=self.properties['target'],
            new=self.presence_manager.HomeStates.home.value,
            constrain_input_boolean=self.enabled_entity_id)

    def arrived_home(self, event_name: str, data: dict, kwargs: dict) -> None:
        """Start a timer after the person has arrived."""
        self.run_in(self.check_for_tile, self.properties['duration'])

    def check_for_tile(self, kwargs: dict) -> None:
        """Notify the person if their Tile is missing."""
        tile = self.get_state(self.entities['tile'], attribute='all')
        if tile['state'] == 'home':
            return

        self.notification_manager.send(
            "Missing Valuable",
            'Is {0} at home?'.format(tile['attributes']['friendly_name']),
            target=self.properties['target'],
            data={
                'push': {
                    'category': 'map'
                },
                'action_data': {
                    'latitude': str(tile['attributes']['latitude']),
                    'longitude': str(tile['attributes']['longitude'])
                }
            })
