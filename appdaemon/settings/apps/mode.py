"""Define a mode."""
from typing import List, Union

from core import Base


class Mode(Base):
    """Define a mode."""

    def configure(self) -> None:
        """Configure."""
        self._enabled_toggles_to_disable = []  # type: List[str]
        self._enabled_toggles_to_enable = []  # type: List[str]
        self.switch = 'input_boolean.mode_{0}'.format(self.name)

        self.listen_state(self.switch_turned_off_cb, self.switch, new='off')
        self.listen_state(self.switch_turned_on_cb, self.switch, new='on')

    @property
    def state(self) -> str:
        """Return the current state of the mode switch."""
        return self.get_state(self.switch)

    def activate(self) -> None:
        """Activate the mode."""
        self.turn_on(self.switch)

    def deactivate(self) -> None:
        """Deactivate the mode."""
        self.turn_off(self.switch)

    def register_enabled_entity(
            self, enabled_entity_id: str, value: str) -> None:
        """Record how a enable toggle should respond when in this mode."""
        location = getattr(self, '_enabled_toggles_to_{0}'.format(value))
        if enabled_entity_id in location:
            return

        location.append(enabled_entity_id)

    def switch_turned_off_cb(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Respond when the mode is turned off."""
        for enabled_toggle in self._enabled_toggles_to_disable:
            self.turn_on(enabled_toggle)
        for enabled_toggle in self._enabled_toggles_to_enable:
            self.turn_off(enabled_toggle)

    def switch_turned_on_cb(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Respond when the mode is turned on."""
        for enabled_toggle in self._enabled_toggles_to_enable:
            self.turn_on(enabled_toggle)
        for enabled_toggle in self._enabled_toggles_to_disable:
            self.turn_off(enabled_toggle)
