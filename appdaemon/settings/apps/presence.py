"""Define apps related to presence."""
# pylint: disable=attribute-defined-outside-init

from enum import Enum
from typing import Union

from automation import Base  # type: ignore
from people import PEOPLE_KEY  # type: ignore


class PresenceManager(Base):
    """Define a class to represent a presence manager."""

    class HomeStates(Enum):
        """Define an enum for presence states."""

        away = 'Away'
        extended_away = 'Extended Away'
        home = 'Home'
        just_arrived = 'Just Arrived'
        just_left = 'Just Left'

    class ProximityStates(Enum):
        """Define an enum for proximity states."""

        away = 'away'
        edge = 'edge'
        home = 'home'
        nearby = 'nearby'

    PROXIMITY_SENSOR = 'proximity.home'

    HOME_THRESHOLD = 0
    NEARBY_THRESHOLD = 5280
    EDGE_THRESHOLD = 15840

    @property
    def proximity(self) -> int:
        """Return the current proximity."""
        try:
            return int(self.get_state(self.PROXIMITY_SENSOR))
        except ValueError:
            return 0

    def initialize(self) -> None:
        """Initialize."""
        super().initialize()

        if self.proximity == self.HOME_THRESHOLD:
            self.state = self.ProximityStates.home
        elif self.HOME_THRESHOLD < self.proximity <= self.NEARBY_THRESHOLD:
            self.state = self.ProximityStates.nearby
        else:
            self.state = self.ProximityStates.away

        self.listen_state(
            self._proximity_change_cb,
            self.PROXIMITY_SENSOR,
            attribute='all',
            duration=60)

        for person in self.global_vars[PEOPLE_KEY]:
            # Set initial presence (so a restart can unstick it):
            if person.raw_location == 'home':
                person.presence_input_select = self.HomeStates.home
            else:
                person.presence_input_select = self.HomeStates.away

            # Fire events when presence changes:
            self.listen_state(
                self._presence_change_cb,
                person.presence_input_select,
                person=person)

            # (Extended) Away -> Just Arrived
            self.listen_state(
                self._change_input_select_cb,
                person.at_home_sensor,
                old='off',
                new='on',
                person=person,
                target_state=self.HomeStates.just_arrived)

            # Just Arrived -> Home
            self.listen_state(
                self._change_input_select_cb,
                person.presence_input_select,
                new=self.HomeStates.just_arrived.value,
                duration=60 * 5,
                person=person,
                target_state=self.HomeStates.home)

            # Just Left -> Just Arrived = Home
            self.listen_state(
                self._change_input_select_cb,
                person.presence_input_select,
                old=self.HomeStates.just_left.value,
                new=self.HomeStates.just_arrived.value,
                person=person,
                target_state=self.HomeStates.home)

            # Home -> Just Left
            self.listen_state(
                self._change_input_select_cb,
                person.at_home_sensor,
                old='on',
                new='off',
                person=person,
                target_state=self.HomeStates.just_left)

            # Just Left -> Away
            self.listen_state(
                self._change_input_select_cb,
                person.presence_input_select,
                new=self.HomeStates.just_left.value,
                duration=60 * 5,
                person=person,
                target_state=self.HomeStates.away)

            # Away -> Extended Away
            self.listen_state(
                self._change_input_select_cb,
                person.presence_input_select,
                new=self.HomeStates.away.value,
                duration=60 * 60 * 24,
                person=person,
                target_state=self.HomeStates.extended_away)

    def _change_input_select_cb(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Change state of a home presence input select."""
        person = kwargs['person']
        target_state = kwargs['target_state']

        self.log(
            'Presence entity change for "{0}": {1} -> {2}'.format(
                entity, old, new),
            level='DEBUG')
        self.log(
            'Changing presence input select: {0} -> {1}'.format(
                person.presence_input_select, target_state.value),
            level='DEBUG')

        person.presence_input_select = target_state

    def _presence_change_cb(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Fire an event when a device tracker changes state."""
        if old == new:
            return

        new_state = self.HomeStates(new)
        if new_state in (self.HomeStates.just_arrived, self.HomeStates.home):
            states = [self.HomeStates.just_arrived, self.HomeStates.home]
        else:
            states = [new_state]

        person = kwargs['person']
        first = self.only_one(*states)

        self.log(
            'Presence change for {0}: {1} -> {2} (first: {3})'.format(
                person.first_name, old, new, first),
            level='DEBUG')

        self.fire_event(
            'PRESENCE_CHANGE',
            person=person.first_name,
            old=old,
            new=new,
            first=first)

    def _proximity_change_cb(  # pylint: disable=too-many-arguments
            self, entity: Union[str, dict], attribute: str, old: dict,
            new: dict, kwargs: dict) -> None:
        """Lock up when we leave home."""
        if old['state'] == 'not set' or new['state'] == 'not set':
            return

        new_proximity = int(new['state'])
        old_state = self.state

        if (self.state != self.ProximityStates.home
                and new_proximity == self.HOME_THRESHOLD):
            self.state = self.ProximityStates.home
        elif (self.state != self.ProximityStates.nearby and
              self.HOME_THRESHOLD < new_proximity <= self.NEARBY_THRESHOLD):
            self.state = self.ProximityStates.nearby
        elif (self.state != self.ProximityStates.edge and
              self.NEARBY_THRESHOLD < new_proximity <= self.EDGE_THRESHOLD):
            self.state = self.ProximityStates.edge
        elif (self.state != self.ProximityStates.away
              and new_proximity > self.NEARBY_THRESHOLD):
            self.state = self.ProximityStates.away

        if self.state != old_state:
            self.log('Proximity event: {0}'.format(self.state.value))
            self.fire_event(
                'PROXIMITY_CHANGE', old=old_state.value, new=self.state.value)

    def _whos_in_state(self, *states: Enum) -> list:
        """Return a list people who are in a certain set of states."""
        return [
            person for person in self.global_vars[PEOPLE_KEY]
            if self.get_state(person.presence_input_select) in [
                state.value for state in states
            ]
        ]

    def anyone(self, *states: Enum) -> bool:
        """Determine whether *any* person is in one or more states."""
        if self._whos_in_state(*states):
            return True

        return False

    def everyone(self, *states: Enum) -> bool:
        """Determine whether *every* person is in one or more states."""
        if self._whos_in_state(*states) == self.global_vars[PEOPLE_KEY]:
            return True

        return False

    def noone(self, *states: Enum) -> bool:
        """Determine whether *no* person is in one or more states."""
        if not self._whos_in_state(*states):
            return True

        return False

    def only_one(self, *states: Enum) -> bool:
        """Determine whether *only one* person is in one or more states."""
        return len(self._whos_in_state(*states)) == 1

    def whos_away(self, include_others: bool = True) -> list:
        """Return a list of notifiers who are away."""
        if include_others:
            return self._whos_in_state(
                self.HomeStates.away, self.HomeStates.extended_away,
                self.HomeStates.just_left)

        return self._whos_in_state(self.HomeStates.away)

    def whos_extended_away(self) -> list:
        """Return a list of notifiers who are away."""
        return self._whos_in_state(self.HomeStates.extended_away)

    def whos_home(self, include_others: bool = True) -> list:
        """Return a list of notifiers who are at home."""
        if include_others:
            return self._whos_in_state(
                self.HomeStates.home, self.HomeStates.just_arrived)

        return self._whos_in_state(self.HomeStates.home)

    def whos_just_arrived(self) -> list:
        """Return a list of notifiers who are at home."""
        return self._whos_in_state(self.HomeStates.just_arrived)

    def whos_just_left(self) -> list:
        """Return a list of notifiers who are at home."""
        return self._whos_in_state(self.HomeStates.just_left)
