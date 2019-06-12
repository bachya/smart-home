"""Define a mode."""
from const import EVENT_MODE_CHANGE
from core import Base


class Mode(Base):
    """Define a mode."""

    @property
    def state(self) -> str:
        """Return the current state of the mode switch."""
        return self.get_state(self._switch)

    def on_disable(self) -> None:
        """Deactivate the mode when its input boolean is toggled off."""
        self.log("Deactivating mode: {0}".format(self.name))
        self.fire_event(EVENT_MODE_CHANGE, name=self.name, state="off")

    def on_enable(self) -> None:
        """Deactivate the mode when its input boolean is toggled on."""
        self.log("Activating mode: {0}".format(self.name))
        self.fire_event(EVENT_MODE_CHANGE, name=self.name, state="on")
