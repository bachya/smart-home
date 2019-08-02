"""Define apps related to presence."""
from enum import Enum
from typing import Union

from core import Base
from const import CONF_PEOPLE, EVENT_PROXIMITY_CHANGE

CONF_EDGE_THRESHOLD = "edge_threshold"
CONF_HOME_THRESHOLD = "home_threshold"
CONF_NEARBY_THRESHOLD = "nearby_threshold"
CONF_PROXIMITY_ZONE_SENSOR = "proximity_zone_sensor"

DEFAULT_EDGE_THRESHOLD = 3 * 5280
DEFAULT_HOME_THRESHOLD = 0 * 5280
DEFAULT_NEARBY_THRESHOLD = 7 * 5280


class PresenceManager(Base):
    """Define a class to represent a presence manager."""

    class HomeStates(Enum):
        """Define an enum for presence states."""

        away = "Away"
        extended_away = "Extended Away"
        home = "Home"
        just_arrived = "Just Arrived"
        just_left = "Just Left"

    class ProximityZones(Enum):
        """Define an enum for proximity states."""

        away = "Away"
        edge = "Edge"
        home = "Home"
        nearby = "Nearby"

    def configure(self) -> None:
        """Configure."""
        self.listen_state(
            self._on_proximity_zone_change,
            self.entity_ids[CONF_PROXIMITY_ZONE_SENSOR],
            duration=60,
        )

    @property
    def edge_threshold(self) -> int:
        """Return the number of feet away from home when "edge" starts."""
        try:
            return int(self.get_state(self.entity_ids[CONF_EDGE_THRESHOLD])) * 5280
        except TypeError:
            return DEFAULT_EDGE_THRESHOLD

    @property
    def home_threshold(self) -> int:
        """Return the number of feet away from home when "home" starts."""
        try:
            return int(self.get_state(self.entity_ids[CONF_HOME_THRESHOLD])) * 5280
        except TypeError:
            return DEFAULT_HOME_THRESHOLD

    @property
    def nearby_threshold(self) -> int:
        """Return the number of feet away from home when "nearby" starts."""
        try:
            return int(self.get_state(self.entity_ids[CONF_NEARBY_THRESHOLD])) * 5280
        except TypeError:
            return DEFAULT_NEARBY_THRESHOLD

    @property
    def proximity_zone(self) -> "ProximityZones":
        """Return the current proximity zone."""
        return self.ProximityZones(
            self.get_state(self.entity_ids[CONF_PROXIMITY_ZONE_SENSOR])
        )

    def _on_proximity_zone_change(
        self,
        entity: Union[str, dict],
        attribute: str,
        old: dict,
        new: dict,
        kwargs: dict,
    ) -> None:
        """Lock up when we leave home."""
        self.fire_event(EVENT_PROXIMITY_CHANGE, old=old, new=new)

    def _whos_in_state(self, *states: "HomeStates") -> list:
        """Return a list people who are in a certain set of states."""
        return [
            person
            for person in self.global_vars[CONF_PEOPLE]
            if person.non_binary_state in states
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
