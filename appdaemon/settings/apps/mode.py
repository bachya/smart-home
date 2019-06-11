"""Define a mode."""
from typing import Union

from const import EVENT_MODE_CHANGE
from core import Base


class Mode(Base):
    """Define a mode."""

    @property
    def state(self) -> str:
        """Return the current state of the mode switch."""
        return self.get_state(self._switch)

    def on_disabled(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Deactivate the mode when its input boolean is toggled off."""
        self.log("Deactivating mode: {0}".format(self.name))
        self.fire_event(EVENT_MODE_CHANGE, name=self.name, state="off")

    def on_enabled(
        self, entity: Union[str, dict], attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """Deactivate the mode when its input boolean is toggled on."""
        self.log("Activating mode: {0}".format(self.name))
        self.fire_event(EVENT_MODE_CHANGE, name=self.name, state="on")
