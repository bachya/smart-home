"""Define apps related to presence."""
from enum import Enum
from typing import Union

from core import Base
from const import CONF_PEOPLE, EVENT_PROXIMITY_CHANGE


class PresenceManager(Base):
    """Define a class to represent a presence manager."""

    class HomeStates(Enum):
        """Define an enum for presence states."""

        away = "Away"
        extended_away = "Extended Away"
        home = "Home"
        just_arrived = "Just Arrived"
        just_left = "Just Left"

    class ProximityStates(Enum):
        """Define an enum for proximity states."""

        away = "away"
        edge = "edge"
        home = "home"
        nearby = "nearby"

    PROXIMITY_SENSOR = "proximity.home"

    HOME_THRESHOLD = 0
    NEARBY_THRESHOLD = 15840
    EDGE_THRESHOLD = 31680

    def configure(self) -> None:
        """Configure."""
        if self.proximity == self.HOME_THRESHOLD:
            self.state = self.ProximityStates.home
        elif self.HOME_THRESHOLD < self.proximity <= self.NEARBY_THRESHOLD:
            self.state = self.ProximityStates.nearby
        else:
            self.state = self.ProximityStates.away

        self.listen_state(
            self._proximity_change_cb,
            self.PROXIMITY_SENSOR,
            attribute="all",
            duration=60,
        )

    @property
    def proximity(self) -> int:
        """Return the current proximity."""
        try:
            return int(self.get_state(self.PROXIMITY_SENSOR))
        except ValueError:
            return 0

    def _proximity_change_cb(
        self,
        entity: Union[str, dict],
        attribute: str,
        old: dict,
        new: dict,
        kwargs: dict,
    ) -> None:
        """Lock up when we leave home."""
        if old["state"] == "not set" or new["state"] == "not set":
            return

        new_proximity = int(new["state"])
        old_state = self.state

        if (
            self.state != self.ProximityStates.home
            and new_proximity == self.HOME_THRESHOLD
        ):
            self.state = self.ProximityStates.home
        elif (
            self.state != self.ProximityStates.nearby
            and self.HOME_THRESHOLD < new_proximity <= self.NEARBY_THRESHOLD
        ):
            self.state = self.ProximityStates.nearby
        elif (
            self.state != self.ProximityStates.edge
            and self.NEARBY_THRESHOLD < new_proximity <= self.EDGE_THRESHOLD
        ):
            self.state = self.ProximityStates.edge
        elif (
            self.state != self.ProximityStates.away
            and new_proximity > self.NEARBY_THRESHOLD
        ):
            self.state = self.ProximityStates.away

        if self.state != old_state:
            self.fire_event(
                EVENT_PROXIMITY_CHANGE, old=old_state.value, new=self.state.value
            )

    def _whos_in_state(self, *states: "HomeStates") -> list:
        """Return a list people who are in a certain set of states."""
        return [
            person
            for person in self.global_vars[CONF_PEOPLE]
            if person.home_state in states
        ]

    def anyone(self, *states: "HomeStates") -> bool:
        """Determine whether *any* person is in one or more states."""
        if self._whos_in_state(*states):
            return True

        return False

    def everyone(self, *states: "HomeStates") -> bool:
        """Determine whether *every* person is in one or more states."""
        if self._whos_in_state(*states) == self.global_vars[CONF_PEOPLE]:
            return True

        return False

    def noone(self, *states: "HomeStates") -> bool:
        """Determine whether *no* person is in one or more states."""
        if not self._whos_in_state(*states):
            return True

        return False

    def only_one(self, *states: "HomeStates") -> bool:
        """Determine whether *only one* person is in one or more states."""
        return len(self._whos_in_state(*states)) == 1

    def whos_away(self, include_others: bool = True) -> list:
        """Return a list of notifiers who are away."""
        if include_others:
            return self._whos_in_state(
                self.HomeStates.away,
                self.HomeStates.extended_away,
                self.HomeStates.just_left,
            )

        return self._whos_in_state(self.HomeStates.away)

    def whos_extended_away(self) -> list:
        """Return a list of notifiers who are away."""
        return self._whos_in_state(self.HomeStates.extended_away)

    def whos_home(self, include_others: bool = True) -> list:
        """Return a list of notifiers who are at home."""
        if include_others:
            return self._whos_in_state(
                self.HomeStates.home, self.HomeStates.just_arrived
            )

        return self._whos_in_state(self.HomeStates.home)

    def whos_just_arrived(self) -> list:
        """Return a list of notifiers who are at home."""
        return self._whos_in_state(self.HomeStates.just_arrived)

    def whos_just_left(self) -> list:
        """Return a list of notifiers who are at home."""
        return self._whos_in_state(self.HomeStates.just_left)
