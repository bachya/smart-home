"""Define a mode."""
from typing import Union

from core import Base


class Mode(Base):
    """Define a mode."""

    def configure(self) -> None:
        """Configure."""
        self._enabled_toggles_to_disable = []  # type: ignore
        self._enabled_toggles_to_enable = []  # type: ignore
        self.switch = 'input_boolean.mode_{0}'.format(self.name)

        self.listen_state(self.switch_toggled_cb, self.switch)

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

    def switch_toggled_cb(
            self, entity: Union[str, dict], attribute: str, old: str, new: str,
            kwargs: dict) -> None:
        """Make alterations when a mode enabled_toggle is toggled."""
        if new == 'on':
            func1 = self.turn_off
            func2 = self.turn_on
        else:
            func1 = self.turn_on
            func2 = self.turn_off

        for enabled_toggle in self._enabled_toggles_to_disable:
            func1(enabled_toggle)
        for enabled_toggle in self._enabled_toggles_to_enable:
            func2(enabled_toggle)
